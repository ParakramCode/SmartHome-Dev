"""
telegram.py — Telegram dev/test channel.

A thin adapter: it turns Telegram updates into Dispatcher.handle() calls and
sends the reply back. All real logic (auth, parsing, execution, logging) lives
in the shared core, so Telegram and WhatsApp behave identically.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from ..config import settings
from ..core import Dispatcher
from .. import registry

logger = logging.getLogger(__name__)


def build_app(dispatcher: Dispatcher) -> Application:
    """Build the Telegram Application wired to the shared dispatcher."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        known = registry.get_by_telegram(user.id)
        if known:
            await update.message.reply_text(
                f"Hey {user.first_name}! 👋 You're set up for flat {known.flat}.\n"
                "Just tell me what to do — e.g. 'AC on', 'lights off', 'lock door', "
                "or 'goodnight'. Hindi/Hinglish works too.\n/clear resets our chat."
            )
        else:
            await update.message.reply_text(
                f"Hey {user.first_name}! 👋 I'm your SmartHome assistant, but this "
                f"Telegram account isn't registered yet.\nYour Telegram ID is "
                f"`{user.id}` — share it with building management to get set up.",
                parse_mode="Markdown",
            )

    async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        known = registry.get_by_telegram(update.effective_user.id)
        if known:
            dispatcher.clear_history(known.id)
        await update.message.reply_text("🧹 Conversation history cleared!")

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (update.message.text or "").strip()
        chat_id = update.effective_chat.id
        tid = update.effective_user.id
        if not text:
            return

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        async def notify(msg: str) -> None:
            await context.bot.send_message(chat_id=chat_id, text=msg)

        reply = await dispatcher.handle(
            channel="telegram", message=text, telegram_id=tid, notify=notify,
        )
        await update.message.reply_text(reply)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("Telegram channel built.")
    return app
