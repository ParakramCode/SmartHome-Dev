"""
llm.py — Gemini intent parser (the hybrid parser's fallback).

Used when the pattern matcher can't confidently handle a message. Sends the
message (plus recent history) to Gemini with a system prompt built from the
canonical device types and scenes, and returns a validated Intent. Any failure
falls back to an "unclear" Intent — this path never raises.

If GEMINI_API_KEY is unset, the parser is disabled and returns None so callers
can fall back to a pattern-only flow.
"""

from __future__ import annotations

import json
import asyncio
import logging

from ..config import settings, device_types, scenes
from ..intents import Intent, from_llm_dict, fallback
from .. import lang as lang_mod

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
MAX_TOKENS = 512

# Lazily-created client (only if the LLM is enabled).
_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai  # imported lazily so the dep is optional
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _build_system_prompt() -> str:
    device_list = "\n".join(
        f"  - {name} (Home Assistant domain: {dt.get('domain')})"
        for name, dt in device_types().items()
    )
    scene_list = ""
    for scene_name, actions in scenes().items():
        steps = ", ".join(f"{a['device']}:{a['action']}" for a in actions)
        scene_list += f"  - {scene_name}: [{steps}]\n"

    return f"""You are a smart home assistant for an Indian household.
You understand English, Hindi, and Hinglish (mixed Hindi-English) naturally.

Your job: parse the user's message into a single JSON command to control smart home devices.
Use ONLY the canonical device keys below (not entity IDs) — each flat maps these to its own devices.

=== AVAILABLE DEVICES (use these exact keys) ===
{device_list}

=== AVAILABLE SCENES ===
{scene_list}

=== OUTPUT FORMAT ===
Return ONLY valid JSON. No preamble, no markdown, no code fences. Just raw JSON.

Schema:
{{
  "action": "turn_on|turn_off|lock|unlock|set_temperature|scene|schedule|query|energy|help|unclear",
  "device": "<device key from the list above, or null>",
  "scene": "<scene name from the list above, or null>",
  "scheduled_time": "<HH:MM in 24hr format, or null>",
  "duration_minutes": "<integer number of minutes, or null>",
  "temperature": "<integer degrees, or null>",
  "target_action": "<for schedule only: turn_on|turn_off|lock|unlock, or null>",
  "recurrence": "<for schedule only: daily|once, or null>",
  "confidence": "high|medium|low",
  "reply": "<short conversational reply in the SAME language the user wrote in>"
}}

=== RULES ===
1. Leaving phrases ("I'm leaving", "bahar ja raha hoon") -> action "scene", scene "leaving_home".
2. Goodnight phrases ("good night", "so raha hoon") -> action "scene", scene "goodnight".
3. Arriving phrases ("I'm home", "ghar aa gaya") -> action "scene", scene "i_am_home".
4. "<device> on for X minutes" -> action "turn_on", duration_minutes X.
5. Asking about a device's state -> action "query".
6. Scheduling ("every day at 6am turn on geyser", "kal subah 7 baje AC chalu karna") ->
   action "schedule", scheduled_time "HH:MM", recurrence "daily" or "once",
   target_action the operation (turn_on/turn_off/lock/unlock), device the device.
7. Device not in the list -> action "unclear", explain you don't have that device.
8. Unsure what the user wants -> action "unclear", confidence "low", ask for clarification.
9. Setting a temperature -> action "set_temperature", device "ac", temperature <int>.
10. Asking about energy/electricity usage or bill -> action "energy".
10b. Asking for help, a menu, or what they can control -> action "help".
11. LANGUAGE: reply in the SAME language as the user's CURRENT message ONLY.
    English message -> reply in English. Romanized Hinglish -> reply in Hinglish.
    Devanagari Hindi -> reply in Devanagari Hindi. Do NOT default to Hindi/Hinglish
    for an English message, and do NOT switch languages based on earlier messages.
12. Keep replies short, friendly, conversational — like a helpful housemate.
13. For locks use action "lock"/"unlock", not "turn_on"/"turn_off".
"""


async def parse(user_message: str, conversation_history: list[dict]) -> Intent | None:
    """Parse a message via Gemini. Returns None if the LLM is disabled."""
    if not settings.llm_enabled:
        return None

    from google.genai import types

    # Steer the reply language to the user's current message (strongest signal).
    lang_code = lang_mod.detect(user_message)
    system_prompt = _build_system_prompt() + (
        f"\n\n=== REPLY LANGUAGE (STRICT) ===\n"
        f"The user's current message is in {lang_mod.LABELS[lang_code]}. "
        f"Write the 'reply' field ONLY in {lang_mod.LABELS[lang_code]}, "
        f"matching its script. Ignore the language of any earlier messages."
    )

    contents = []
    for msg in conversation_history:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    logger.info("LLM parse -> model=%s msg='%s' history=%d", MODEL, user_message[:80], len(conversation_history))

    raw_text = ""
    try:
        def _call():
            return _get_client().models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=MAX_TOKENS,
                    temperature=0.2,
                ),
            )

        response = await asyncio.to_thread(_call)
        raw_text = (response.text or "").strip()
        logger.info("LLM raw: %s", raw_text[:300])

        json_str = raw_text
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[-1]
            json_str = json_str.rsplit("```", 1)[0].strip()

        data = json.loads(json_str)
        if not {"action", "reply"}.issubset(data.keys()):
            logger.warning("LLM response missing required keys: %s", data)
            return fallback()
        return from_llm_dict(data)

    except json.JSONDecodeError as exc:
        logger.error("LLM JSON parse failed: %s — raw: %s", exc, raw_text)
        return fallback()
    except Exception as exc:
        logger.exception("LLM unexpected error: %s", exc)
        return fallback()
