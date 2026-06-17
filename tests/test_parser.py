"""Pattern matcher: the brief's command list, Hinglish, and edge cases."""

import pytest

from smarthome.parser import patterns


@pytest.mark.parametrize("text,action,device", [
    ("AC on", "turn_on", "ac"),
    ("ac off", "turn_off", "ac"),
    ("turn on AC", "turn_on", "ac"),
    ("AC ON", "turn_on", "ac"),            # ALL CAPS
    ("lights on", "turn_on", "lights"),
    ("turn off lights", "turn_off", "lights"),
    ("light off", "turn_off", "lights"),
    ("lock door", "lock", "lock"),
    ("lock", "lock", "lock"),
    ("unlock door", "unlock", "lock"),
    ("unlock", "unlock", "lock"),
    ("door unlock", "unlock", "lock"),
    ("batti jalao", "turn_on", "lights"),  # Hinglish
])
def test_known_commands(text, action, device):
    m = patterns.match(text)
    assert m is not None, f"{text!r} should match"
    assert m.action == action
    assert m.device == device


@pytest.mark.parametrize("text", ["ac offf", "", "   ", "😀", "hello there", "asdf"])
def test_unrecognized_defers(text):
    # Garbage / typos / empty must not crash and must defer to the LLM (None).
    assert patterns.match(text) is None


def test_temperature():
    m = patterns.match("ac 24 degree pe set karo")
    assert m.action == "set_temperature" and m.temperature == 24


@pytest.mark.parametrize("text,temp", [
    ("set ac to 24", 24),
    ("ac 22", 22),
    ("set the ac to 18", 18),
])
def test_temperature_bare_number(text, temp):
    m = patterns.match(text)
    assert m.action == "set_temperature" and m.temperature == temp


def test_ac_on_with_duration_not_temperature():
    # "30" here is a duration, not a temperature.
    m = patterns.match("ac on for 30 minutes")
    assert m.action == "turn_on" and m.duration_minutes == 30 and m.temperature is None


def test_duration():
    m = patterns.match("geyser on for 30 minutes")
    assert m.action == "turn_on" and m.device == "geyser" and m.duration_minutes == 30


@pytest.mark.parametrize("text,scene", [
    ("goodnight", "goodnight"),
    ("i am home", "i_am_home"),
    ("bahar ja raha hoon", "leaving_home"),
])
def test_scenes(text, scene):
    m = patterns.match(text)
    assert m.action == "scene" and m.scene == scene


def test_query():
    m = patterns.match("is the ac on?")
    assert m.action == "query" and m.device == "ac"


def test_energy():
    assert patterns.match("my energy usage").action == "energy"


@pytest.mark.parametrize("text", [
    "every day at 6am turn on geyser",
    "turn on geyser at 7pm",
    "kal subah geyser chalu karna",
])
def test_schedule_cues_defer(text):
    # Time-of-day phrasing must defer to the LLM (so it's scheduled, not run now).
    assert patterns.match(text) is None


@pytest.mark.parametrize("text", ["help", "menu", "what can you do", "my devices", "madad"])
def test_help(text):
    assert patterns.match(text).action == "help"


def test_duration_capped():
    m = patterns.match("geyser on for 99999 minutes")
    assert m.action == "turn_on" and m.duration_minutes == 24 * 60


def test_scene_phrase_word_boundary():
    # "goodbye" must NOT trigger the goodnight scene (substring false positive).
    m = patterns.match("goodbye everyone")
    assert m is None or m.action != "scene"
