"""Dispatcher pipeline: auth, rate limiting, logging, and rapid commands."""

import pytest

from smarthome import messages, command_log
from smarthome.core import Dispatcher


async def test_unregistered_rejected(ha):
    d = Dispatcher(ha=ha)
    reply = await d.handle(channel="telegram", message="lights on", telegram_id=999)
    assert reply == messages.NOT_REGISTERED


async def test_registered_command_runs(ha, user):
    d = Dispatcher(ha=ha)
    reply = await d.handle(channel="telegram", message="lights on", telegram_id=user.telegram_id)
    assert reply == "Lights on ✓"


async def test_command_is_logged(ha, user):
    d = Dispatcher(ha=ha)
    await d.handle(channel="whatsapp", message="ac off", whatsapp_number=user.whatsapp_number)
    logs = command_log.recent()
    assert logs and logs[0]["raw_message"] == "ac off"
    assert logs[0]["success"] == 1
    assert logs[0]["parse_source"] == "pattern"


async def test_rate_limit(ha, user):
    d = Dispatcher(ha=ha)
    last = ""
    for _ in range(25):
        last = await d.handle(channel="whatsapp", message="lights on", whatsapp_number=user.whatsapp_number)
    assert last == messages.RATE_LIMITED


async def test_rapid_commands_all_execute(ha, user):
    # 5 commands within the limit should all succeed (no race / no crash).
    d = Dispatcher(ha=ha)
    for _ in range(5):
        reply = await d.handle(channel="telegram", message="lock door", telegram_id=user.telegram_id)
        assert reply == "Door locked ✓"


async def test_empty_message(ha, user):
    d = Dispatcher(ha=ha)
    reply = await d.handle(channel="telegram", message="   ", telegram_id=user.telegram_id)
    assert reply == messages.UNKNOWN
