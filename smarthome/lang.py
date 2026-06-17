"""
lang.py — Language detection + localized replies.

The bot must answer in the SAME language the user wrote in:
  - English          -> English
  - romanized Hindi  -> Hinglish
  - Devanagari Hindi -> Hindi

detect() classifies a message. confirm()/query()/system() produce replies in
that language for the pattern path. The LLM path is steered by a per-message
instruction (see parser/llm.py). English delegates to messages.py so existing
wording/tests stay stable.
"""

from __future__ import annotations

import re

from . import messages

LABELS = {
    "en": "English",
    "hinglish": "Hinglish (romanized Hindi + English, Latin script)",
    "hi": "Hindi (Devanagari script)",
}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Romanized-Hindi markers (padded with spaces to avoid matching inside words).
_HINGLISH_MARKERS = (
    " chalu", " chaalu", " chala", " chalao", " band ", " bandh", " karo", " kar do",
    " kardo", " kar di", " kar de", " diya", " diye", " jala", " jalao", " bujha",
    " bujhao", " khol", " darwaza", " batti", " lagao", " baje", " kya ", " mera ",
    " meri ", " ghar ", " garam", " thanda", " chahiye", " krdo", " kr do", " band",
)


def detect(text: str) -> str:
    """Return 'hi' (Devanagari), 'hinglish' (romanized), or 'en'."""
    if _DEVANAGARI.search(text or ""):
        return "hi"
    low = " " + (text or "").lower().strip() + " "
    if any(m in low for m in _HINGLISH_MARKERS):
        return "hinglish"
    return "en"


# --- Localized device names + action phrases (non-English; en uses messages.py) ---
_DEVICE = {
    "lights": {"hinglish": "Lights", "hi": "लाइट"},
    "ac": {"hinglish": "AC", "hi": "एसी"},
    "geyser": {"hinglish": "Geyser", "hi": "गीज़र"},
    "plug": {"hinglish": "Plug", "hi": "प्लग"},
    "lock": {"hinglish": "Darwaza", "hi": "दरवाज़ा"},
}
_ACTION = {
    "turn_on": {"hinglish": "chalu kar diya", "hi": "चालू कर दिया"},
    "turn_off": {"hinglish": "band kar diya", "hi": "बंद कर दिया"},
    "lock": {"hinglish": "lock kar diya", "hi": "लॉक कर दिया"},
    "unlock": {"hinglish": "khol diya", "hi": "खोल दिया"},
    "set_temperature": {"hinglish": "{t}° pe set kar diya", "hi": "{t}° पर सेट कर दिया"},
}

_SYSTEM = {
    "unknown": {
        "hinglish": "Samajh nahi aaya. Aise likhein: 'AC on', 'lights off', ya 'lock door'.",
        "hi": "समझ नहीं आया। ऐसे लिखें: 'AC on', 'lights off', या 'दरवाज़ा बंद करो'।",
    },
    "not_registered": {
        "hinglish": "Aap registered nahi hain. Building management se baat karein.",
        "hi": "आप रजिस्टर्ड नहीं हैं। कृपया बिल्डिंग मैनेजमेंट से संपर्क करें।",
    },
    "ha_down": {
        "hinglish": "Home system abhi available nahi hai. Thodi der baad try karein.",
        "hi": "होम सिस्टम अभी उपलब्ध नहीं है। थोड़ी देर बाद कोशिश करें।",
    },
    "rate_limited": {
        "hinglish": "Aap bahut tezi se commands bhej rahe hain. Thoda ruk jaayein.",
        "hi": "आप बहुत तेज़ी से कमांड भेज रहे हैं। थोड़ा रुकें।",
    },
    "no_such_device": {
        "hinglish": "Aapke flat mein {device} set up nahi hai.",
        "hi": "आपके फ्लैट में {device} सेट अप नहीं है।",
    },
}

_EN_SYSTEM = {
    "unknown": messages.UNKNOWN,
    "not_registered": messages.NOT_REGISTERED,
    "ha_down": messages.HA_DOWN,
    "rate_limited": messages.RATE_LIMITED,
    "no_such_device": messages.NO_SUCH_DEVICE,
}


def device_name(device: str, lang: str = "en") -> str:
    if lang == "en":
        return device
    return _DEVICE.get(device, {}).get(lang, device)


def confirm(device: str, action: str, lang: str = "en", temperature: int | None = None) -> str:
    """Localized confirmation for a device action."""
    if lang == "en":
        return messages.confirm(device, action, temperature=temperature) if temperature is not None \
            else messages.confirm(device, action)
    phrase = _ACTION.get(action, {}).get(lang)
    if not phrase:
        return messages.confirm(device, action, temperature=temperature) if temperature is not None \
            else messages.confirm(device, action)
    if "{t}" in phrase:
        phrase = phrase.format(t=temperature)
    return f"{device_name(device, lang)} {phrase} ✓"


def query(device: str, state: str, lang: str = "en") -> str:
    name = device_name(device, lang)
    if lang == "hi":
        return f"{name} अभी {state} है।"
    if lang == "hinglish":
        return f"{name} abhi {state} hai."
    return f"{name} is currently {state}."


def system(key: str, lang: str = "en", **fmt) -> str:
    """Localized system message (errors, rejections)."""
    if lang != "en":
        s = _SYSTEM.get(key, {}).get(lang)
        if s:
            return s.format(**fmt) if fmt else s
    en = _EN_SYSTEM[key]
    return en.format(**fmt) if fmt else en
