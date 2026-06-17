"""
core.py — The channel-agnostic command pipeline.

One Dispatcher instance is shared by every channel (WhatsApp, Telegram). It
owns the Home Assistant client, per-user conversation history, and the rate
limiter, and runs each message through the full pipeline:

    resolve user -> rate limit -> parse -> execute -> log -> reply

Channels are thin adapters: they translate their platform's payload into a
handle() call and send the returned string back to the user.
"""

from __future__ import annotations

import time
import logging
from typing import Awaitable, Callable

from .config import settings
from .ha_client import HomeAssistantClient
from .ratelimit import RateLimiter
from . import registry, parser, executor, command_log, messages, memory
from .intents import Intent
from .registry import User

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str], Awaitable[None]]

# Replies that represent a failure (for success accounting in logs).
_FAILURE_REPLIES = {messages.HA_DOWN, messages.ERROR, messages.RATE_LIMITED}


class Dispatcher:
    def __init__(self, ha: HomeAssistantClient | None = None):
        self.ha = ha or HomeAssistantClient()
        self.rate = RateLimiter()
        self._history: dict[int, list[dict]] = {}
        # Optional hook set by the scheduler module (task: scheduling).
        self.schedule_handler = None

    # -- conversation history (persistent, SQLite-backed) ---------------------
    def _history_for(self, user_id: int) -> list[dict]:
        # Lazily load a user's stored history into the in-memory cache so it
        # survives restarts (the bot "remembers" past exchanges).
        if user_id not in self._history:
            self._history[user_id] = memory.load_recent(user_id, settings.conversation_history * 2)
        return self._history[user_id]

    def _remember(self, user_id: int, role: str, content: str) -> None:
        limit = settings.conversation_history * 2
        hist = self._history_for(user_id)
        hist.append({"role": role, "content": content})
        if len(hist) > limit:
            self._history[user_id] = hist[-limit:]
        # Persist + trim so memory outlives restarts.
        memory.add_message(user_id, role, content)
        memory.trim(user_id, limit)

    def clear_history(self, user_id: int) -> None:
        self._history.pop(user_id, None)
        memory.clear(user_id)

    # -- main entry point -----------------------------------------------------
    async def handle(
        self,
        *,
        channel: str,
        message: str,
        whatsapp_number: str | None = None,
        telegram_id: int | None = None,
        notify: NotifyFn | None = None,
    ) -> str:
        """Run a single inbound message through the pipeline; return the reply."""
        started = time.monotonic()
        message = (message or "").strip()

        # 1) Resolve the user (authorization).
        user: User | None = None
        if whatsapp_number:
            user = registry.get_by_whatsapp(whatsapp_number)
        elif telegram_id is not None:
            user = registry.get_by_telegram(telegram_id)

        if user is None:
            command_log.log_command(
                channel=channel, user=None, raw_message=message, intent=None,
                entity_id=None, success=False,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_message="unregistered",
            )
            return messages.NOT_REGISTERED

        # 2) Rate limit.
        if not self.rate.allow(f"{channel}:{user.id}"):
            logger.warning("Rate limited user id=%d on %s", user.id, channel)
            return messages.RATE_LIMITED

        if not message:
            return messages.UNKNOWN

        # 3) Parse.
        intent: Intent = await parser.parse(message, self._history_for(user.id))

        # 4) Execute.
        try:
            reply = await executor.execute(
                intent, user, self.ha, notify=notify, on_schedule=self.schedule_handler,
            )
            error_message = None
        except Exception as exc:
            logger.exception("Executor error: %s", exc)
            reply = messages.ERROR
            error_message = str(exc)

        # 5) Bookkeeping.
        self._remember(user.id, "user", message)
        self._remember(user.id, "assistant", intent.reply or reply)
        registry.touch_activity(user.id)

        success = error_message is None and reply not in _FAILURE_REPLIES and intent.action != "unclear"
        command_log.log_command(
            channel=channel, user=user, raw_message=message, intent=intent,
            entity_id=user.resolve(intent.device) if intent.device else None,
            success=success,
            latency_ms=int((time.monotonic() - started) * 1000),
            error_message=error_message,
        )
        return reply

    async def close(self) -> None:
        await self.ha.close()
