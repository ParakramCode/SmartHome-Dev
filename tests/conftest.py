"""Shared test fixtures: an isolated temp DB and a stub Home Assistant client."""

import tempfile
from pathlib import Path

import pytest

from smarthome import db, registry
from smarthome.config import settings


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Point the DB at a fresh temp file for every test."""
    tmp = Path(tempfile.mkdtemp()) / "test.db"
    monkeypatch.setattr(db, "DB_PATH", tmp)
    db.init_db()
    yield
    for p in tmp.parent.glob("test.db*"):
        p.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Keep tests offline: never call the real LLM, even if a key is in .env."""
    monkeypatch.setattr(settings, "gemini_api_key", None)


class StubHA:
    """In-memory Home Assistant double that records calls."""

    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []
        self.state = "off"

    async def turn_on(self, e): self.calls.append(("turn_on", e)); return self.ok
    async def turn_off(self, e): self.calls.append(("turn_off", e)); return self.ok
    async def lock(self, e): self.calls.append(("lock", e)); return self.ok
    async def unlock(self, e): self.calls.append(("unlock", e)); return self.ok
    async def set_temperature(self, e, t): self.calls.append(("set_temperature", e, t)); return self.ok
    async def get_state(self, e): return self.state
    async def get_attributes(self, e): return {"energy": 5.0}
    async def ping(self): return self.ok
    async def close(self): pass


@pytest.fixture
def ha():
    return StubHA()


@pytest.fixture
def user():
    return registry.add_user(
        flat="B-204",
        entities={
            "ac": "climate.b204_ac",
            "lights": "light.b204_main",
            "lock": "lock.b204_door",
            "geyser": "switch.b204_geyser",
        },
        whatsapp_number="919876543210",
        telegram_id=12345,
        name="Test Resident",
    )
