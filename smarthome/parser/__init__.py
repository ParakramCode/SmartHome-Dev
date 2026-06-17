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
from .. import lang as lang_mod
from . import patterns
from . import llm

logger = logging.getLogger(__name__)


async def parse(user_message: str, conversation_history: list[dict] | None = None) -> Intent:
    """Parse a user message into an Intent (pattern first, then LLM)."""
    history = conversation_history or []

    # Truncate overly long messages before parsing (per the brief).
    message = user_message.strip()[: settings.max_message_chars * 5]
    lang_code = lang_mod.detect(message)

    # 1) Fast path.
    intent = patterns.match(message)
    if intent is not None:
        intent.lang = lang_code
        logger.info("Parsed by pattern: action=%s device=%s scene=%s lang=%s",
                    intent.action, intent.device, intent.scene, lang_code)
        return intent

    # 2) LLM fallback.
    intent = await llm.parse(message, history)
    if intent is not None:
        intent.lang = lang_code
        logger.info("Parsed by LLM: action=%s device=%s scene=%s conf=%s lang=%s",
                    intent.action, intent.device, intent.scene, intent.confidence, lang_code)
        return intent

    # 3) No pattern match and no LLM available — reply in the user's language.
    logger.info("No pattern match and LLM disabled — returning unclear.")
    return Intent(action="unclear", confidence="low",
                  reply=lang_mod.system("unknown", lang_code), source="none", lang=lang_code)
