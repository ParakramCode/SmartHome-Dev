"""
main.py — Entry point for the SmartHome platform.

Boots everything in one asyncio process:
    - SQLite
    - Home Assistant client + shared Dispatcher
    - WhatsApp channel (if configured) wired into the FastAPI webhook
    - Telegram channel (if configured) via long-polling
    - APScheduler for scheduled commands
    - Reliability watchdog
    - FastAPI app (webhook + admin panel) served by uvicorn

Run:  python main.py
"""

from __future__ import annotations

import logging
import asyncio

import uvicorn

from smarthome import config
from smarthome.config import settings
from smarthome import db, voice
from smarthome.core import Dispatcher
from smarthome.registry import User
from smarthome.channels.whatsapp import WhatsAppChannel
from smarthome.web.app import create_app
from smarthome.scheduler import CommandScheduler
from smarthome.watchdog import Watchdog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for noisy in ("httpx", "httpcore", "telegram", "apscheduler"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("smarthome.main")


async def run() -> None:
    config.print_startup_summary()
    db.init_db()

    dispatcher = Dispatcher()

    # --- WhatsApp channel (production) ---
    wa_channel: WhatsAppChannel | None = None
    if settings.whatsapp_enabled:
        wa_channel = WhatsAppChannel(dispatcher)
        if voice.available():
            wa_channel.transcribe = lambda audio_id: voice.transcribe_whatsapp(wa_channel.client, audio_id)
            logger.info("Voice-note transcription enabled.")
        logger.info("WhatsApp channel ready.")

    tg_app = None  # set below; referenced by the notifier closures

    # --- Cross-channel notifiers (for scheduler + watchdog) ---
    async def notify_user(user: User, text: str) -> None:
        if user.whatsapp_number and wa_channel:
            await wa_channel.client.send_text(user.whatsapp_number, text)
        elif user.telegram_id and tg_app:
            await tg_app.bot.send_message(chat_id=user.telegram_id, text=text)

    async def notify_admin(text: str) -> None:
        if settings.admin_whatsapp and wa_channel:
            await wa_channel.client.send_text(settings.admin_whatsapp, text)
        else:
            logger.warning("Admin alert (no WhatsApp admin configured): %s", text)

    # --- Scheduler ---
    scheduler = CommandScheduler(dispatcher, notifier=notify_user)
    dispatcher.schedule_handler = scheduler.add
    scheduler.start()

    # --- Watchdog ---
    watchdog = Watchdog(dispatcher.ha, notify_admin=notify_admin)
    watchdog.start()

    # --- Web server (webhook + admin) — start it CONCURRENTLY so it's always
    #     reachable even if a channel's startup is slow. ---
    app = create_app(dispatcher, whatsapp_channel=wa_channel)
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_level="info")
    )
    server_task = asyncio.create_task(server.serve())

    # --- Telegram channel (dev), guarded with timeouts so a slow/flaky init
    #     can never block the rest of the app. ---
    if settings.telegram_enabled:
        try:
            import importlib
            # Import off-thread: the python-telegram-bot import is heavy and disk
            # reads can be slow (e.g. iCloud-synced dirs), which would otherwise
            # freeze the event loop and the web server.
            logger.info("Telegram: importing module…")
            tg_module = await asyncio.wait_for(
                asyncio.to_thread(importlib.import_module, "smarthome.channels.telegram"),
                timeout=60,
            )
            logger.info("Telegram: building application…")
            tg_app = tg_module.build_app(dispatcher)
            logger.info("Telegram: initializing…")
            await asyncio.wait_for(tg_app.initialize(), timeout=30)
            await tg_app.start()
            await asyncio.wait_for(
                tg_app.updater.start_polling(drop_pending_updates=True, allowed_updates=["message"]),
                timeout=30,
            )
            logger.info("Telegram polling started.")
        except Exception:
            logger.exception("Telegram startup failed — running without Telegram.")
            tg_app = None

    print("\n  ✅  SmartHome is live.")
    print(f"      Webhook + admin : http://localhost:{settings.port}/admin")
    print(f"      Health          : http://localhost:{settings.port}/health")
    print("      Press Ctrl+C to stop.\n")

    try:
        await server_task  # blocks until shutdown signal
    finally:
        logger.info("Shutting down…")
        if tg_app:
            try:
                if tg_app.updater and tg_app.updater.running:
                    await tg_app.updater.stop()
                await tg_app.stop()
                await tg_app.shutdown()
            except Exception as exc:
                logger.warning("Telegram shutdown error: %s", exc)
        await watchdog.stop()
        scheduler.shutdown()
        await dispatcher.close()
        if wa_channel:
            await wa_channel.client.close()
        logger.info("Bye.")


def main() -> None:
    print("\n" + "=" * 60)
    print("  🤖  SmartHome AI Platform — starting…")
    print("=" * 60)
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
