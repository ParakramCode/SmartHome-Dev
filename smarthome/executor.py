"""
executor.py — Turn an Intent into Home Assistant actions for a specific flat.

Channel-agnostic: WhatsApp and Telegram both call execute(). Entity IDs are
resolved per-user via the registry, so the same intent controls different
physical devices depending on who sent it. Returns the reply text to send back.

Optional hooks:
    notify(text)        — async callback for delayed messages (auto-off)
    on_schedule(intent) — async callback to persist a scheduled command
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from .config import scenes as get_scenes, device_types
from .intents import Intent
from .ha_client import HomeAssistantClient
from .registry import User
from . import messages, energy, bg, lang

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str], Awaitable[None]]
ScheduleFn = Callable[[Intent, User], Awaitable[str]]


async def _auto_off(
    ha: HomeAssistantClient, entity_id: str, minutes: int,
    label: str, notify: NotifyFn | None,
) -> None:
    """Turn a device off after `minutes`, then notify the user."""
    logger.info("Auto-off scheduled: %s in %d min", entity_id, minutes)
    await asyncio.sleep(minutes * 60)
    ok = await ha.turn_off(entity_id)
    if notify:
        msg = (
            f"⏰ Auto-off: {label} turned off after {minutes} min."
            if ok else f"⚠️ Auto-off failed for {label}. Please turn it off manually."
        )
        await notify(msg)
    logger.info("Auto-off %s for %s", "done" if ok else "FAILED", entity_id)


def _help_text(user: User) -> str:
    """Personalised help: the user's own devices + example commands."""
    devices = sorted(user.entities.keys())
    scene_names = sorted(get_scenes().keys())
    if devices:
        device_line = "I can control: " + ", ".join(devices) + "."
    else:
        device_line = "Your flat doesn't have any devices set up yet."
    examples = [
        "• 'AC on' / 'lights off' / 'lock door'",
        "• 'set AC to 24' · 'geyser on for 30 minutes'",
        "• 'is the AC on?' · 'my energy usage'",
        "• 'every day at 6am turn on geyser' · 'show my schedules'",
    ]
    if scene_names:
        examples.append("• scenes: " + ", ".join(s.replace("_", " ") for s in scene_names))
    return f"👋 {device_line}\n\nTry:\n" + "\n".join(examples) + "\n\nHindi/Hinglish works too."


async def _run_scene(scene_name: str, user: User, ha: HomeAssistantClient) -> tuple[bool, list[str]]:
    """Run every action in a scene, resolving devices to this flat's entities."""
    scene = get_scenes().get(scene_name)
    if scene is None:
        return False, [f"Scene '{scene_name}' not found."]

    results: list[str] = []
    all_ok = True
    for step in scene:
        device, action = step["device"], step["action"]
        entity = user.resolve(device)
        if not entity:
            results.append(f"  • {device}: not in your flat (skipped)")
            continue  # missing device in a scene is tolerated, not a failure
        ok = await _do_action(ha, action, entity)
        results.append(f"  {'✓' if ok else '✗'} {device}: {action.replace('_', ' ')}")
        all_ok = all_ok and ok
    return all_ok, results


async def _do_action(ha: HomeAssistantClient, action: str, entity_id: str, temperature: int | None = None) -> bool:
    if action == "turn_on":
        return await ha.turn_on(entity_id)
    if action == "turn_off":
        return await ha.turn_off(entity_id)
    if action == "lock":
        return await ha.lock(entity_id)
    if action == "unlock":
        return await ha.unlock(entity_id)
    if action == "set_temperature":
        ok = await ha.set_temperature(entity_id, temperature) if temperature else False
        return ok and await ha.turn_on(entity_id)
    return False


async def execute(
    intent: Intent,
    user: User,
    ha: HomeAssistantClient,
    *,
    notify: NotifyFn | None = None,
    on_schedule: ScheduleFn | None = None,
) -> str:
    """Execute an intent for a user and return the reply text."""
    action = intent.action

    # --- Scene ---
    if action == "scene" and intent.scene:
        ok, details = await _run_scene(intent.scene, user, ha)
        header = intent.reply or (f"Scene '{intent.scene}' done." if ok else f"Scene '{intent.scene}' had issues.")
        return header + "\n" + "\n".join(details)

    # --- Scheduling ---
    if action == "schedule":
        if on_schedule:
            return await on_schedule(intent, user)
        return intent.reply or "Scheduling isn't available right now."

    # --- Humidifier: set humidity % ---
    if action == "set_humidity" and intent.device:
        entity = user.resolve(intent.device)
        if not entity:
            return lang.system("no_such_device", intent.lang, device=intent.device)
        ok = await ha.set_humidity(entity, intent.humidity)
        if ok:
            await ha.turn_on(entity)  # ensure it's running
        if not ok:
            return lang.system("ha_down", intent.lang)
        return intent.reply or f"Humidity set to {intent.humidity}% ✓"

    # --- Humidifier: set mist/preset mode ---
    if action == "set_mode" and intent.device:
        entity = user.resolve(intent.device)
        if not entity:
            return lang.system("no_such_device", intent.lang, device=intent.device)
        ok = await ha.set_mode(entity, intent.mode)
        if ok:
            await ha.turn_on(entity)
        if not ok:
            return lang.system("ha_down", intent.lang)
        return intent.reply or f"Mode set to {intent.mode} ✓"

    # --- Energy report ---
    if action == "energy":
        return await energy.report_for(user, ha)

    # --- Help / what can I control ---
    if action == "help":
        return _help_text(user)

    # --- State query ---
    if action == "query" and intent.device:
        entity = user.resolve(intent.device)
        if not entity:
            return lang.system("no_such_device", intent.lang, device=intent.device)
        state = await ha.get_state(entity)
        if state is None:
            return lang.system("ha_down", intent.lang)
        prefix = intent.reply + "\n" if intent.reply else ""
        return prefix + lang.query(intent.device, state, intent.lang)

    # --- Device control (incl. temperature) ---
    if action in ("turn_on", "turn_off", "lock", "unlock", "set_temperature") and intent.device:
        entity = user.resolve(intent.device)
        if not entity:
            return lang.system("no_such_device", intent.lang, device=intent.device)

        # turn_on carrying a temperature is treated as set_temperature.
        effective = action
        if action == "turn_on" and intent.temperature and intent.device == "ac":
            effective = "set_temperature"

        ok = await _do_action(ha, effective, entity, temperature=intent.temperature)
        if not ok:
            return lang.system("ha_down", intent.lang)

        reply = intent.reply or lang.confirm(intent.device, effective, intent.lang, temperature=intent.temperature)

        # Auto-off timer.
        if effective == "turn_on" and intent.duration_minutes:
            bg.spawn(
                _auto_off(ha, entity, intent.duration_minutes, intent.device, notify),
                name=f"auto_off:{entity}",
            )
            reply += messages.AUTO_OFF_NOTE.format(minutes=intent.duration_minutes)
        return reply

    # --- Unclear / fallback ---
    return intent.reply or lang.system("unknown", intent.lang)
