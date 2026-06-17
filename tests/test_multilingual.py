"""Parser coverage for romanized Hinglish AND proper Hindi (Devanagari)."""

import pytest

from smarthome.parser import patterns


# --- Romanized Hinglish ---
@pytest.mark.parametrize("text,action,device", [
    ("batti jalao", "turn_on", "lights"),
    ("batti band karo", "turn_off", "lights"),
    ("geyser chalu karo", "turn_on", "geyser"),
    ("ac band kar do", "turn_off", "ac"),
    ("darwaza khol do", "unlock", "lock"),
    ("darwaza band karo", "lock", "lock"),
])
def test_hinglish_devices(text, action, device):
    m = patterns.match(text)
    assert m is not None, f"{text!r} should match"
    assert (m.action, m.device) == (action, device)


# --- Proper Hindi (Devanagari) ---
@pytest.mark.parametrize("text,action,device", [
    ("लाइट चालू करो", "turn_on", "lights"),
    ("लाइट बंद करो", "turn_off", "lights"),
    ("एसी चालू करो", "turn_on", "ac"),
    ("गीज़र चालू कर दो", "turn_on", "geyser"),
    ("गीजर बंद करो", "turn_off", "geyser"),
    ("दरवाज़ा बंद करो", "lock", "lock"),
    ("दरवाज़ा खोलो", "unlock", "lock"),
    ("प्लग ऑन करो", "turn_on", "plug"),
])
def test_hindi_devices(text, action, device):
    m = patterns.match(text)
    assert m is not None, f"{text!r} should match"
    assert (m.action, m.device) == (action, device)


@pytest.mark.parametrize("text,temp", [
    ("एसी 24 डिग्री", 24),
    ("एसी २४ डिग्री", 24),          # Devanagari numerals
    ("एसी को 22 कर दो", 22),
])
def test_hindi_temperature(text, temp):
    m = patterns.match(text)
    assert m.action == "set_temperature" and m.temperature == temp


def test_hindi_duration():
    m = patterns.match("गीज़र ३० मिनट के लिए चालू करो")
    assert m.action == "turn_on" and m.device == "geyser" and m.duration_minutes == 30


@pytest.mark.parametrize("text,scene", [
    ("शुभ रात्रि", "goodnight"),
    ("गुड नाइट", "goodnight"),
    ("मैं बाहर जा रहा हूँ", "leaving_home"),
    ("मैं घर आ गया", "i_am_home"),
])
def test_hindi_scenes(text, scene):
    m = patterns.match(text)
    assert m.action == "scene" and m.scene == scene


def test_hindi_query():
    m = patterns.match("क्या एसी चालू है?")
    assert m.action == "query" and m.device == "ac"


def test_hindi_energy():
    assert patterns.match("बिजली का बिल").action == "energy"


def test_hindi_help():
    assert patterns.match("मदद").action == "help"


def test_hindi_schedule_defers():
    # "every day at 6am turn on geyser" in Hindi -> defer to the LLM, not run now.
    assert patterns.match("रोज़ सुबह 6 बजे गीज़र चालू करो") is None
