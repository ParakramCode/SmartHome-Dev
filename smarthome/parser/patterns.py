"""
patterns.py — Fast, deterministic command matcher.

Handles the common, unambiguous commands (and a few Hindi/Hinglish keywords)
without an API call. Returns an Intent on a confident match, or None to let
the LLM take over. Precision matters more than recall here: when in doubt,
return None and defer to the LLM.
"""

from __future__ import annotations

import re

from ..config import scenes as get_scenes, device_types
from ..intents import Intent

# Canonical device type -> recognised synonyms (matched as whole words).
DEVICE_SYNONYMS = {
    "ac": ["ac", "a.c", "air con", "aircon", "air conditioner", "cooler"],
    "lights": ["light", "lights", "lamp", "bulb", "batti", "laitu"],
    "lock": ["door", "lock", "gate", "darwaza", "darwazaa", "darwaaza"],
    "geyser": ["geyser", "geezer", "water heater", "heater", "boiler"],
    "plug": ["plug", "socket", "switch"],
}

ON_WORDS = ["on", "chalu", "chaalu", "start", "jala", "jalao", "chala", "chalao", "lagao"]
OFF_WORDS = ["off", "band", "bandh", "close", "bujha", "bujhao", "rok", "khatam"]
UNLOCK_WORDS = ["unlock", "open", "khol", "kholo", "kholdo"]
LOCK_WORDS = ["lock", "band", "lagao", "tala"]

QUERY_PREFIXES = ("is ", "are ", "kya ", "what ", "whats ", "what's ")
QUERY_WORDS = ["status", "on hai", "chal raha", "chalu hai", "band hai", "kitna"]

# Words implying a future/recurring time -> the message is a schedule, not an
# immediate command. Defer these to the LLM.
SCHEDULE_CUES = ("tomorrow", "tonight", "everyday", "every day", "daily", "roz", "subah", "shaam", "kal")

# Help / capability discovery.
HELP_PHRASES = (
    "help", "menu", "madad", "what can you do", "what can i", "how to use",
    "commands", "kya kar sakte", "kaise use", "what devices", "my devices",
)

# Cap auto-off duration to a sane maximum (24h) to avoid runaway timers.
MAX_DURATION_MINUTES = 24 * 60

# Scene trigger phrases (in addition to the scene name itself).
SCENE_PHRASES = {
    "goodnight": ["goodnight", "good night", "so raha", "sone ja", "sleeping", "shubh ratri"],
    "leaving_home": ["leaving", "going out", "ja raha", "bahar ja", "i'm out", "im out", "nikal raha"],
    "i_am_home": ["i'm home", "im home", "i am home", "ghar aa", "aa gaya", "back home", "ghar pe"],
}

_WORD = re.compile(r"[a-z0-9']+")
_DURATION_RE = re.compile(r"(\d+)\s*(?:m|min|mins|minit|minute|minutes)\b")
_TEMP_RE = re.compile(r"(\d{2})\s*(?:degree|degrees|deg|°|c\b)")


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("°", " degree ")
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_word(text: str, phrase: str) -> bool:
    """Whole-word/phrase containment (avoids matching 'on' inside 'iron')."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _find_device(text: str) -> str | None:
    valid = device_types()
    for device, synonyms in DEVICE_SYNONYMS.items():
        if device not in valid:
            continue
        for syn in synonyms:
            if _contains_word(text, syn):
                return device
    return None


def _find_scene(text: str) -> str | None:
    scenes = get_scenes()
    for scene in scenes:
        if _contains_word(text, scene.replace("_", " ")) or _contains_word(text, scene):
            return scene
    for scene, phrases in SCENE_PHRASES.items():
        if scene not in scenes:
            continue
        for phrase in phrases:
            if _contains_word(text, phrase):
                return scene
    return None


def _is_query(text: str) -> bool:
    if text.endswith("?"):
        return True
    if text.startswith(QUERY_PREFIXES):
        return True
    return any(_contains_word(text, q) for q in QUERY_WORDS)


def _any(text: str, words: list[str]) -> bool:
    return any(_contains_word(text, w) for w in words)


def match(text: str) -> Intent | None:
    """Return a confident Intent, or None to defer to the LLM."""
    norm = _normalize(text)
    if not norm:
        return None

    # 0-) Help / menu / what can I control.
    if any(p in norm for p in HELP_PHRASES):
        return Intent(action="help", confidence="high", source="pattern")

    # 0) Energy / usage / bill enquiry.
    if any(w in norm for w in ("energy", "usage", "electricity", "bijli", "bill", "consumption", "units")):
        return Intent(action="energy", confidence="high", source="pattern")

    # 0b) Listing / cancelling schedules (creating one needs a time -> LLM).
    if "schedule" in norm or "reminder" in norm:
        has_time = re.search(r"\d{1,2}\s*(?::|am|pm|baje|bje)", norm)
        if not has_time:
            if any(w in norm for w in ("cancel", "clear", "delete", "remove", "stop")):
                return Intent(action="schedule", target_action="cancel", source="pattern")
            return Intent(action="schedule", target_action="list", source="pattern")
        return None  # has a time -> let the LLM build the full schedule

    # 0c) Future/recurring time cues mean "schedule this" — defer to the LLM so
    # it isn't mistaken for an immediate command. (Duration like "for 30 min"
    # has no such cue and still pattern-matches below.)
    if (
        any(c in norm for c in SCHEDULE_CUES)
        or re.search(r"\b\d{1,2}\s*(?:am|pm)\b", norm)
        or re.search(r"\bat\s+\d{1,2}\b", norm)
        or "baje" in norm or "bje" in norm
    ):
        return None

    # 1) Scenes take priority (a single phrase, multiple devices).
    scene = _find_scene(norm)
    if scene:
        return Intent(action="scene", scene=scene, confidence="high", source="pattern")

    # 2) Device commands.
    device = _find_device(norm)
    if not device:
        # Bare "unlock" / "khol" with no device named implies the door.
        if _contains_word(norm, "unlock") or _contains_word(norm, "khol"):
            return Intent(action="unlock", device="lock", confidence="high", source="pattern")
        return None

    # 2a) Status query about the device.
    if _is_query(norm):
        return Intent(action="query", device=device, confidence="high", source="pattern")

    duration_match = _DURATION_RE.search(norm)
    duration = int(duration_match.group(1)) if duration_match else None
    if duration is not None:
        duration = min(duration, MAX_DURATION_MINUTES)

    # 2b) Lock-type devices map on/off + open/close to lock/unlock.
    if device == "lock":
        if _any(norm, UNLOCK_WORDS):
            return Intent(action="unlock", device=device, confidence="high", source="pattern")
        if _any(norm, LOCK_WORDS):
            return Intent(action="lock", device=device, confidence="high", source="pattern")
        return None  # ambiguous "door" with no verb -> let LLM decide

    # 2c) AC temperature ("ac 24 degree", "set ac to 22").
    if device == "ac":
        temp_match = _TEMP_RE.search(norm)
        if temp_match:
            temp = int(temp_match.group(1))
            if 16 <= temp <= 32:
                return Intent(
                    action="set_temperature", device=device,
                    temperature=temp, confidence="high", source="pattern",
                )

    # 2d) On / off.
    if _any(norm, ON_WORDS):
        return Intent(
            action="turn_on", device=device, duration_minutes=duration,
            confidence="high", source="pattern",
        )
    if _any(norm, OFF_WORDS):
        return Intent(action="turn_off", device=device, confidence="high", source="pattern")

    # Device named but no clear verb -> defer to the LLM.
    return None
