"""
llm.py — Claude AI intent parser for SmartHome AI Bot.

Sends user messages to Claude Haiku with a dynamic system prompt
containing available devices and scenes. Returns structured JSON
with the parsed intent, or a safe fallback on any failure.
"""

import json
import logging

import anthropic

from config import ENV, CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client & model
# ---------------------------------------------------------------------------
_client = anthropic.Anthropic(api_key=ENV["ANTHROPIC_API_KEY"])
MODEL = "claude-haiku-20240307"
MAX_TOKENS = 512

# ---------------------------------------------------------------------------
# Fallback intent returned when parsing fails
# ---------------------------------------------------------------------------
FALLBACK_INTENT = {
    "action": "unclear",
    "device": None,
    "scene": None,
    "scheduled_time": None,
    "duration_minutes": None,
    "temperature": None,
    "confidence": "low",
    "reply": "Something went wrong, please try again.",
}


def _build_system_prompt() -> str:
    """Build the system prompt dynamically from config.yaml."""

    devices = CONFIG.get("devices", {})
    scenes = CONFIG.get("scenes", {})

    device_list = "\n".join(
        f"  - {name} -> entity_id: {eid}" for name, eid in devices.items()
    )
    scene_list = ""
    for scene_name, actions in scenes.items():
        steps = ", ".join(
            f"{a['device']}:{a['action']}" for a in actions
        )
        scene_list += f"  - {scene_name}: [{steps}]\n"

    return f"""You are a smart home assistant for an Indian household.
You understand English, Hindi, and Hinglish (mixed Hindi-English) naturally.

Your job: parse the user's message into a single JSON command to control smart home devices.

=== AVAILABLE DEVICES ===
{device_list}

=== AVAILABLE SCENES ===
{scene_list}

=== OUTPUT FORMAT ===
Return ONLY valid JSON. No preamble, no markdown, no explanation, no code fences. Just raw JSON.

Schema:
{{
  "action": "turn_on|turn_off|lock|unlock|scene|schedule|query|unclear",
  "device": "<device key from the list above, or null>",
  "scene": "<scene name from the list above, or null>",
  "scheduled_time": "<HH:MM in 24hr format, or null>",
  "duration_minutes": "<integer number of minutes, or null>",
  "temperature": "<integer degrees, or null>",
  "confidence": "high|medium|low",
  "reply": "<short conversational reply in the SAME language the user wrote in>"
}}

=== RULES ===
1. "I'm leaving" or "main ja raha hoon" or "bahar ja raha hoon" -> action: "scene", scene: "leaving_home"
2. "Goodnight" or "good night" or "so raha hoon" or "sone ja raha hoon" -> action: "scene", scene: "goodnight"
3. "I'm home" or "main aa gaya" or "ghar aa gaya" -> action: "scene", scene: "i_am_home"
4. "Geyser on for X minutes" or "geyser X minute ke liye chalu kar do" -> action: "turn_on", device: "geyser", duration_minutes: X
5. If the user asks about the state/status of a device -> action: "query", device: "<device key>"
6. If the user wants to schedule something for a specific time -> action: "schedule", scheduled_time: "<HH:MM>"
7. If the device mentioned is NOT in the available devices list -> action: "unclear", reply: explain you don't know that device
8. If you are unsure what the user wants -> action: "unclear", confidence: "low", reply: ask for clarification
9. If the user sets a temperature -> include the temperature field, action: "turn_on", device: "bedroom_ac"
10. Always reply in the same language the user wrote in (English, Hindi, or Hinglish).
11. Keep replies short, friendly, and conversational — like a helpful housemate.
12. For lock-related commands use action "lock" or "unlock", not "turn_on"/"turn_off".

=== EXAMPLES ===
User: "Turn on the geyser"
{{"action":"turn_on","device":"geyser","scene":null,"scheduled_time":null,"duration_minutes":null,"temperature":null,"confidence":"high","reply":"Geyser turned on!"}}

User: "Goodnight"
{{"action":"scene","device":null,"scene":"goodnight","scheduled_time":null,"duration_minutes":null,"temperature":null,"confidence":"high","reply":"Goodnight! Setting up everything for sleep."}}

User: "Geyser 30 minute ke liye chalu kar do"
{{"action":"turn_on","device":"geyser","scene":null,"scheduled_time":null,"duration_minutes":30,"temperature":null,"confidence":"high","reply":"Geyser chalu kar diya, 30 minute baad band ho jayega!"}}

User: "AC 24 degree pe set karo"
{{"action":"turn_on","device":"bedroom_ac","scene":null,"scheduled_time":null,"duration_minutes":null,"temperature":24,"confidence":"high","reply":"AC 24 degree pe set kar diya!"}}

User: "Is the geyser on?"
{{"action":"query","device":"geyser","scene":null,"scheduled_time":null,"duration_minutes":null,"temperature":null,"confidence":"high","reply":"Let me check the geyser status for you."}}
"""


async def parse_intent(
    user_message: str, conversation_history: list[dict]
) -> dict:
    """
    Parse a user message into a structured intent dict using Claude.

    Args:
        user_message: The raw text message from the user.
        conversation_history: List of prior {"role": ..., "content": ...} dicts
                              for multi-turn context.

    Returns:
        A dict matching the JSON schema above, or FALLBACK_INTENT on failure.
    """
    system_prompt = _build_system_prompt()

    # Build messages array: conversation history + current user message
    messages = list(conversation_history)  # shallow copy
    messages.append({"role": "user", "content": user_message})

    logger.info("LLM request  -> model=%s  user_msg='%s'  history_len=%d",
                MODEL, user_message[:100], len(conversation_history))

    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )

        raw_text = response.content[0].text.strip()
        logger.info("LLM raw response: %s", raw_text)

        # Parse JSON — strip markdown fences if the model wraps them anyway
        json_str = raw_text
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[-1]  # remove first ``` line
            json_str = json_str.rsplit("```", 1)[0]  # remove trailing ```
            json_str = json_str.strip()

        intent = json.loads(json_str)

        # Validate required keys exist
        required_keys = {"action", "confidence", "reply"}
        if not required_keys.issubset(intent.keys()):
            logger.warning("LLM response missing required keys: %s",
                           required_keys - intent.keys())
            return {**FALLBACK_INTENT}

        # Fill in any missing optional keys with None
        for key in ("device", "scene", "scheduled_time",
                     "duration_minutes", "temperature"):
            intent.setdefault(key, None)

        logger.info("LLM parsed intent: action=%s device=%s scene=%s confidence=%s",
                     intent["action"], intent.get("device"),
                     intent.get("scene"), intent["confidence"])

        return intent

    except json.JSONDecodeError as exc:
        logger.error("LLM JSON parse failed: %s — raw: %s", exc, raw_text)
        return {**FALLBACK_INTENT}

    except anthropic.APIConnectionError:
        logger.error("LLM API connection failed — check internet / API key")
        return {
            **FALLBACK_INTENT,
            "reply": "Cannot reach the AI service right now, please try again.",
        }

    except anthropic.RateLimitError:
        logger.error("LLM API rate limit hit")
        return {
            **FALLBACK_INTENT,
            "reply": "I'm getting too many requests, please wait a moment.",
        }

    except Exception as exc:
        logger.exception("LLM unexpected error: %s", exc)
        return {**FALLBACK_INTENT}
