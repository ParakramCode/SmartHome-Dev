"""
main.py — Entry point for SmartHome AI Bot.

Starts the Telegram bot with polling. This is the only file you run:
    python main.py

All configuration is loaded automatically from config.py on import.
"""

import logging
import asyncio
import signal
import sys

from bot import build_bot, ha

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Quiet down noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
async def shutdown(app) -> None:
    """Clean up resources on shutdown."""
    logger.info("Shutting down...")
    await ha.close()
    logger.info("Home Assistant client closed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Start the SmartHome AI Bot."""
    print()
    print("=" * 60)
    print("  🤖  SmartHome AI Bot — Starting...")
    print("=" * 60)
    print()

    app = build_bot()

    # Register shutdown callback
    app.post_shutdown = shutdown

    logger.info("Starting Telegram polling...")
    print("  ✅  Bot is live! Send a message on Telegram.")
    print("  Press Ctrl+C to stop.\n")

    # Run the bot with polling (blocks until stopped)
    app.run_polling(
        drop_pending_updates=True,   # ignore messages sent while bot was offline
        allowed_updates=["message"], # only listen for messages
    )


if __name__ == "__main__":
    main()
