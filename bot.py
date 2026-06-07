"""
bot.py — Telegram bot handler for SmartHome AI Bot.

Receives user messages, sends them to the LLM for intent parsing,
executes the parsed intent on Home Assistant, and replies with
a conversational response. Also handles scene execution and
geyser auto-off scheduling.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import ENV, CONFIG
from llm import parse_intent
from ha_client import HomeAssistantClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Home Assistant client — shared across handlers
# ---------------------------------------------------------------------------
ha = HomeAssistantClient()

# ---------------------------------------------------------------------------
# Per-user conversation history  (user_id -> list of messages)
# Simple in-memory store — cleared on restart. Stage 1 only.
# ---------------------------------------------------------------------------
_conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 10  # keep last N exchanges to stay within token limits


def _get_history(user_id: int) -> list[dict]:
    """Get conversation history for a user, creating if needed."""
    if user_id not in _conversations:
        _conversations[user_id] = []
    return _conversations[user_id]


def _append_history(user_id: int, role: str, content: str) -> None:
    """Append a message to user's conversation history, trimming if needed."""
    history = _get_history(user_id)
    history.append({"role": role, "content": content})
    # Keep only the last MAX_HISTORY * 2 messages (pairs of user + assistant)
    if len(history) > MAX_HISTORY * 2:
        _conversations[user_id] = history[-(MAX_HISTORY * 2):]


# ---------------------------------------------------------------------------
# Intent executors
# ---------------------------------------------------------------------------
async def _execute_scene(scene_name: str) -> tuple[bool, list[str]]:
    """
    Execute a scene by running all its actions sequentially.
    Returns (overall_success, list_of_status_messages).
    """
    scenes = CONFIG.get("scenes", {})
    devices = CONFIG.get("devices", {})

    if scene_name not in scenes:
        return False, [f"Scene '{scene_name}' not found in config."]

    actions = scenes[scene_name]
    results = []
    all_ok = True

    for action_def in actions:
        device_key = action_def["device"]
        action = action_def["action"]
        entity_id = devices.get(device_key)

        if not entity_id:
            results.append(f"  ✗ {device_key}: unknown device")
            all_ok = False
            continue

        if action == "turn_on":
            ok = await ha.turn_on(entity_id)
        elif action == "turn_off":
            ok = await ha.turn_off(entity_id)
        elif action == "lock":
            ok = await ha.lock(entity_id)
        elif action == "unlock":
            ok = await ha.unlock(entity_id)
        else:
            results.append(f"  ? {device_key}: unknown action '{action}'")
            all_ok = False
            continue

        status = "✓" if ok else "✗"
        results.append(f"  {status} {device_key}: {action}")
        if not ok:
            all_ok = False

    return all_ok, results


async def _schedule_auto_off(
    entity_id: str, minutes: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Schedule a device to turn off after `minutes` minutes."""
    logger.info(
        "Scheduling auto-off for %s in %d minutes", entity_id, minutes
    )
    await asyncio.sleep(minutes * 60)

    ok = await ha.turn_off(entity_id)
    if ok:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ Auto-off: {entity_id} has been turned off after {minutes} minutes.",
        )
        logger.info("Auto-off completed: %s", entity_id)
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Auto-off failed for {entity_id}. Please turn it off manually.",
        )
        logger.error("Auto-off FAILED: %s", entity_id)


async def _execute_intent(
    intent: dict, context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> str:
    """
    Execute a parsed intent against Home Assistant.
    Returns the final reply text to send to the user.
    """
    action = intent.get("action")
    device_key = intent.get("device")
    scene_name = intent.get("scene")
    reply = intent.get("reply", "Done!")
    duration = intent.get("duration_minutes")
    temperature = intent.get("temperature")

    devices = CONFIG.get("devices", {})

    # ---- Scene execution ----
    if action == "scene" and scene_name:
        ok, details = await _execute_scene(scene_name)
        detail_text = "\n".join(details)
        if ok:
            return f"{reply}\n\n📋 Scene '{scene_name}':\n{detail_text}"
        else:
            return f"{reply}\n\n⚠️ Scene '{scene_name}' had issues:\n{detail_text}"

    # ---- Device control ----
    if action in ("turn_on", "turn_off", "lock", "unlock") and device_key:
        entity_id = devices.get(device_key)
        if not entity_id:
            return f"I don't recognize the device '{device_key}'."

        if action == "turn_on":
            # Handle temperature for AC
            if temperature and "climate" in entity_id:
                ok = await ha.set_temperature(entity_id, temperature)
                if ok:
                    await ha.turn_on(entity_id)
            else:
                ok = await ha.turn_on(entity_id)

            # Schedule auto-off if duration specified
            if ok and duration:
                asyncio.create_task(
                    _schedule_auto_off(entity_id, duration, context, chat_id)
                )
                return f"{reply}\n\n⏱️ Will auto-off in {duration} minutes."

        elif action == "turn_off":
            ok = await ha.turn_off(entity_id)
        elif action == "lock":
            ok = await ha.lock(entity_id)
        elif action == "unlock":
            ok = await ha.unlock(entity_id)

        if ok:
            return reply
        else:
            return f"⚠️ Could not {action.replace('_', ' ')} {device_key}. Home Assistant may be unreachable."

    # ---- State query ----
    if action == "query" and device_key:
        entity_id = devices.get(device_key)
        if not entity_id:
            return f"I don't recognize the device '{device_key}'."

        state = await ha.get_state(entity_id)
        if state:
            return f"{reply}\n\n📊 {device_key} is currently: **{state}**"
        else:
            return f"Couldn't get the status of {device_key} right now."

    # ---- Schedule (future feature placeholder) ----
    if action == "schedule":
        scheduled_time = intent.get("scheduled_time")
        return (
            f"{reply}\n\n🕐 Scheduling is noted for {scheduled_time}, "
            f"but real scheduling is coming in Stage 2!"
        )

    # ---- Unclear / fallback ----
    return reply


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    user = update.effective_user
    logger.info("/start from user %s (id=%d)", user.first_name, user.id)

    await update.message.reply_text(
        f"Hey {user.first_name}! 👋\n\n"
        "I'm your SmartHome AI assistant. Just tell me what you want "
        "in English, Hindi, or Hinglish and I'll handle it.\n\n"
        "Examples:\n"
        "• \"Turn on the geyser\"\n"
        "• \"Goodnight\"\n"
        "• \"Geyser 30 minute ke liye chalu kar do\"\n"
        "• \"AC 24 degree pe set karo\"\n"
        "• \"Is the geyser on?\"\n\n"
        "Type /clear to reset our conversation history."
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /clear command — resets conversation history."""
    user_id = update.effective_user.id
    _conversations.pop(user_id, None)
    logger.info("/clear from user %d", user_id)
    await update.message.reply_text("🧹 Conversation history cleared!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages — the main bot loop."""
    user = update.effective_user
    user_message = update.message.text.strip()
    chat_id = update.effective_chat.id

    if not user_message:
        return

    logger.info(
        "Message from %s (id=%d): '%s'",
        user.first_name, user.id, user_message[:100],
    )

    # Show "typing..." indicator while processing
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Get conversation history for this user
    history = _get_history(user.id)

    # Parse intent via LLM
    intent = await parse_intent(user_message, history)

    logger.info("Parsed intent: %s", intent)

    # Execute the intent against Home Assistant
    reply = await _execute_intent(intent, context, chat_id)

    # Update conversation history
    _append_history(user.id, "user", user_message)
    _append_history(user.id, "assistant", intent.get("reply", reply))

    # Send reply
    await update.message.reply_text(reply)


# ---------------------------------------------------------------------------
# Bot builder
# ---------------------------------------------------------------------------
def build_bot() -> Application:
    """Build and configure the Telegram bot application."""
    token = ENV["TELEGRAM_BOT_TOKEN"]

    app = Application.builder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot application built successfully")
    return app
