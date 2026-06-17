"""
parser — Hybrid command parsing: fast pattern match, LLM fallback.

parse() tries the deterministic pattern matcher first (instant, free). If it
can't confidently handle the message, it defers to the LLM. If the LLM is
disabled (no API key) and patterns didn't match, it returns an "unclear"
intent so the caller can send a help message.
"""

from __future__ import annotations

import logging

from ..config import settings
from ..intents import Intent
from ..messages import UNKNOWN
from . import patterns
from . import llm

logger = logging.getLogger(__name__)


async def parse(user_message: str, conversation_history: list[dict] | None = None) -> Intent:
    """Parse a user message into an Intent (pattern first, then LLM)."""
    history = conversation_history or []

    # Truncate overly long messages before parsing (per the brief).
    message = user_message.strip()[: settings.max_message_chars * 5]

    # 1) Fast path.
    intent = patterns.match(message)
    if intent is not None:
        logger.info("Parsed by pattern: action=%s device=%s scene=%s",
                    intent.action, intent.device, intent.scene)
        return intent

    # 2) LLM fallback.
    intent = await llm.parse(message, history)
    if intent is not None:
        logger.info("Parsed by LLM: action=%s device=%s scene=%s conf=%s",
                    intent.action, intent.device, intent.scene, intent.confidence)
        return intent

    # 3) No pattern match and no LLM available.
    logger.info("No pattern match and LLM disabled — returning unclear.")
    return Intent(action="unclear", confidence="low", reply=UNKNOWN, source="none")
