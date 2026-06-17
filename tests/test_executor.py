"""Executor: device control, scenes, queries, temperature, missing devices."""

import pytest

from smarthome import executor, messages
from smarthome.intents import Intent


async def test_turn_on(ha, user):
    reply = await executor.execute(Intent(action="turn_on", device="lights"), user, ha)
    assert reply == "Lights on ✓"
    assert ("turn_on", "light.b204_main") in ha.calls


async def test_set_temperature(ha, user):
    reply = await executor.execute(
        Intent(action="set_temperature", device="ac", temperature=22), user, ha
    )
    assert "22" in reply
    assert ("set_temperature", "climate.b204_ac", 22) in ha.calls


async def test_unlock(ha, user):
    reply = await executor.execute(Intent(action="unlock", device="lock"), user, ha)
    assert reply == "Door unlocked ✓"


async def test_query(ha, user):
    ha.state = "on"
    reply = await executor.execute(Intent(action="query", device="ac"), user, ha)
    assert "on" in reply


async def test_scene(ha, user):
    reply = await executor.execute(Intent(action="scene", scene="goodnight"), user, ha)
    assert "goodnight" in reply
    # goodnight turns lights+ac off and locks the door
    assert ("turn_off", "light.b204_main") in ha.calls
    assert ("lock", "lock.b204_door") in ha.calls


async def test_missing_device(ha, user):
    # user has no "plug" entity
    reply = await executor.execute(Intent(action="turn_on", device="plug"), user, ha)
    assert reply == messages.NO_SUCH_DEVICE.format(device="plug")


async def test_ha_failure_returns_friendly_error(user):
    from tests.conftest import StubHA
    bad = StubHA(ok=False)
    reply = await executor.execute(Intent(action="turn_on", device="lights"), user, bad)
    assert reply == messages.HA_DOWN


async def test_auto_off_note(ha, user):
    reply = await executor.execute(
        Intent(action="turn_on", device="geyser", duration_minutes=30), user, ha
    )
    assert "30 min" in reply


async def test_energy(ha, user):
    reply = await executor.execute(Intent(action="energy"), user, ha)
    assert "kWh" in reply and "₹" in reply
