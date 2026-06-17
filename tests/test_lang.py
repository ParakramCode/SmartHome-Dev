"""Replies must match the language the user wrote in (en / hinglish / hi)."""

import pytest

from smarthome import lang, executor
from smarthome.intents import Intent
from smarthome.parser import patterns


@pytest.mark.parametrize("text,expected", [
    ("turn it on", "en"),
    ("lights on", "en"),
    ("set ac to 24", "en"),
    ("batti jalao", "hinglish"),
    ("ac band karo", "hinglish"),
    ("geyser chalu kar do", "hinglish"),
    ("लाइट चालू करो", "hi"),
    ("एसी बंद करो", "hi"),
])
def test_detect(text, expected):
    assert lang.detect(text) == expected


@pytest.mark.parametrize("lng,expected", [
    ("en", "Lights on ✓"),
    ("hinglish", "Lights chalu kar diya ✓"),
    ("hi", "लाइट चालू कर दिया ✓"),
])
def test_confirm_language(lng, expected):
    assert lang.confirm("lights", "turn_on", lng) == expected


def test_pattern_sets_lang_via_parser_detect():
    # The pattern matcher itself is language-agnostic; parser sets .lang.
    assert lang.detect("लाइट चालू करो") == "hi"
    assert lang.detect("lights chalu karo") == "hinglish"
    assert lang.detect("turn on the lights") == "en"


async def test_executor_replies_in_language(ha, user):
    # English in -> English out
    en = await executor.execute(Intent(action="turn_on", device="lights", lang="en"), user, ha)
    assert en == "Lights on ✓"
    # Hinglish in -> Hinglish out
    hg = await executor.execute(Intent(action="turn_off", device="lights", lang="hinglish"), user, ha)
    assert hg == "Lights band kar diya ✓"
    # Hindi in -> Hindi out
    hi = await executor.execute(Intent(action="lock", device="lock", lang="hi"), user, ha)
    assert "लॉक" in hi


async def test_no_such_device_localized(ha, user):
    r = await executor.execute(Intent(action="turn_on", device="plug", lang="hi"), user, ha)
    assert "सेट अप नहीं" in r
