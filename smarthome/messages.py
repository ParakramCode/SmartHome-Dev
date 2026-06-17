"""
messages.py — Canonical reply templates.

Used for confirmations on pattern-matched commands and for system replies
(rejections, errors). LLM-parsed commands carry their own conversational
`reply`, so these are the deterministic fallbacks. Kept short (WhatsApp
replies should stay well under 1024 chars).
"""

# Per-device, per-action confirmations. Falls back to a generic line.
CONFIRM = {
    ("ac", "turn_on"): "AC turned on ✓",
    ("ac", "turn_off"): "AC turned off ✓",
    ("ac", "set_temperature"): "AC set to {temperature}° ✓",
    ("lights", "turn_on"): "Lights on ✓",
    ("lights", "turn_off"): "Lights off ✓",
    ("lock", "lock"): "Door locked ✓",
    ("lock", "unlock"): "Door unlocked ✓",
    ("geyser", "turn_on"): "Geyser on ✓",
    ("geyser", "turn_off"): "Geyser off ✓",
    ("plug", "turn_on"): "Plug on ✓",
    ("plug", "turn_off"): "Plug off ✓",
}

GENERIC_OK = "Done ✓"

# System messages.
UNKNOWN = "Didn't catch that. Try: 'AC on', 'lights off', or 'lock door'."
NOT_REGISTERED = "You're not registered. Please contact building management."
ERROR = "Something went wrong. Please try again in a moment."
HA_DOWN = "Home system is temporarily unavailable. Our team has been notified."
RATE_LIMITED = "You're sending commands too fast. Please wait a moment."
NO_SUCH_DEVICE = "Your flat doesn't have a {device} set up."
AUTO_OFF_NOTE = "\n⏱️ Will auto-off in {minutes} min."


def confirm(device: str, action: str, **fmt) -> str:
    """Confirmation line for a device action."""
    template = CONFIRM.get((device, action), GENERIC_OK)
    return template.format(**fmt) if fmt else template
