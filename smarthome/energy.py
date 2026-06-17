"""
energy.py — Energy usage reporting from metering-capable entities.

Reads energy attributes (kWh) exposed by Home Assistant for a flat's devices
(e.g. metering smart plugs) and produces a short, WhatsApp-friendly report
priced at the configured tariff.
"""

from __future__ import annotations

import logging

from .config import settings
from .ha_client import HomeAssistantClient
from .registry import User

logger = logging.getLogger(__name__)

# Attribute names HA devices commonly use to expose cumulative energy in kWh.
_ENERGY_ATTRS = ("energy", "today_energy", "total_energy_kwh", "energy_kwh", "energy_today")


def _extract_kwh(attrs: dict) -> float | None:
    for key in _ENERGY_ATTRS:
        val = attrs.get(key)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                continue
    return None


async def report_for(user: User, ha: HomeAssistantClient) -> str:
    """Build an energy report string for a user's flat."""
    lines: list[str] = []
    total_kwh = 0.0
    found = False

    for device, entity in user.entities.items():
        attrs = await ha.get_attributes(entity)
        if not attrs:
            continue
        kwh = _extract_kwh(attrs)
        if kwh is None:
            continue
        found = True
        total_kwh += kwh
        lines.append(f"  • {device}: {kwh:.2f} kWh")

    if not found:
        return "No energy-metering devices are set up for your flat yet."

    cost = total_kwh * settings.energy_rate_per_unit
    body = "\n".join(lines)
    return (
        f"⚡ Energy usage for {user.flat}:\n{body}\n"
        f"Total: {total_kwh:.2f} kWh ≈ ₹{cost:,.0f} (at ₹{settings.energy_rate_per_unit:g}/unit)"
    )
