"""
intents.py — The shared command model passed from parser to executor.

Both the pattern matcher and the LLM produce an Intent. The executor consumes
it. Keeping one structure means the two parse paths are interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# Valid actions an intent may carry.
ACTIONS = {
    "turn_on",
    "turn_off",
    "lock",
    "unlock",
    "set_temperature",
    "scene",
    "schedule",
    "query",
    "energy",
    "help",
    "unclear",
}


@dataclass
class Intent:
    action: str = "unclear"
    device: str | None = None            # canonical device type (ac, lights, lock, ...)
    scene: str | None = None             # scene name
    scheduled_time: str | None = None    # "HH:MM" 24h
    duration_minutes: int | None = None  # auto-off after N minutes
    temperature: int | None = None       # target degrees (climate)
    target_action: str | None = None     # for action=schedule: what to run at the time
    recurrence: str | None = None        # for action=schedule: "daily" | "once"
    confidence: str = "high"             # high | medium | low
    reply: str = ""                      # conversational reply (LLM fills this)
    source: str = "pattern"              # pattern | llm | none

    def as_dict(self) -> dict:
        return asdict(self)


def fallback(reply: str = "Something went wrong, please try again.") -> Intent:
    """Safe intent for any failure path."""
    return Intent(action="unclear", confidence="low", reply=reply, source="none")


def from_llm_dict(data: dict) -> Intent:
    """Build an Intent from the LLM's JSON, coercing/validating fields."""
    action = data.get("action", "unclear")
    if action not in ACTIONS:
        action = "unclear"

    def _int(val):
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    return Intent(
        action=action,
        device=data.get("device"),
        scene=data.get("scene"),
        scheduled_time=data.get("scheduled_time"),
        duration_minutes=_int(data.get("duration_minutes")),
        temperature=_int(data.get("temperature")),
        target_action=data.get("target_action"),
        recurrence=data.get("recurrence"),
        confidence=data.get("confidence", "medium"),
        reply=data.get("reply", ""),
        source="llm",
    )
