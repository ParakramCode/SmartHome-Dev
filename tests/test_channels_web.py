"""WhatsApp helpers, scheduler triggers, and the FastAPI web layer."""

import json
import hmac
import hashlib

import pytest
from fastapi.testclient import TestClient

from smarthome.config import settings
from smarthome.channels import whatsapp as wa
from smarthome.core import Dispatcher
from smarthome.scheduler import CommandScheduler
from smarthome.intents import Intent
from smarthome.web.app import create_app


# ---- WhatsApp webhook helpers ----
def test_parse_inbound():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919", "type": "text", "text": {"body": "AC on"}}]}}]}]}
    msgs = wa.parse_inbound(payload)
    assert msgs == [{"from": "919", "type": "text", "text": "AC on"}]


def test_verify_webhook():
    assert wa.verify_webhook("subscribe", settings.whatsapp_verify_token, "C") == "C"
    assert wa.verify_webhook("subscribe", "wrong", "C") is None


def test_signature(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_provider", "meta")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "topsecret")
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert wa.verify_signature(body, {"X-Hub-Signature-256": sig}) is True
    assert wa.verify_signature(body, {"X-Hub-Signature-256": "sha256=deadbeef"}) is False


# ---- Scheduler triggers ----
async def test_scheduler_daily(ha, user):
    sch = CommandScheduler(Dispatcher(ha=ha))
    reply = await sch.add(
        Intent(action="schedule", target_action="turn_on", device="geyser",
               scheduled_time="06:00", recurrence="daily"),
        user,
    )
    assert "geyser" in reply
    listed = await sch.add(Intent(action="schedule", target_action="list"), user)
    assert "06:00" in listed
    cancelled = await sch.add(Intent(action="schedule", target_action="cancel"), user)
    assert "1" in cancelled


async def test_scheduler_bad_time(ha, user):
    sch = CommandScheduler(Dispatcher(ha=ha))
    reply = await sch.add(
        Intent(action="schedule", target_action="turn_on", device="ac",
               scheduled_time="bogus", recurrence="daily"),
        user,
    )
    assert "couldn't" in reply.lower()


async def test_scheduled_temperature_runs_set_temperature(ha, user):
    # "every day at 6am turn on AC at 24" should store a set_temperature target.
    sch = CommandScheduler(Dispatcher(ha=ha))
    await sch.add(
        Intent(action="schedule", target_action="turn_on", device="ac",
               temperature=24, scheduled_time="06:00", recurrence="daily"),
        user,
    )
    # fire the stored job and confirm it sets the temperature
    from smarthome import db
    import json
    with db.connect() as conn:
        row = conn.execute("SELECT id, intent FROM schedules WHERE user_id = ?", (user.id,)).fetchone()
    target = json.loads(row["intent"])
    assert target["action"] == "set_temperature"
    await sch._run_job(row["id"], user.id, target)
    assert ("set_temperature", "climate.b204_ac", 24) in ha.calls


# ---- Web layer ----
@pytest.fixture
def client(ha):
    app = create_app(Dispatcher(ha=ha), whatsapp_channel=None)
    return TestClient(app)


def test_webhook_verify(client):
    r = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": settings.whatsapp_verify_token,
        "hub.challenge": "XYZ",
    })
    assert r.status_code == 200 and r.text == "XYZ"


def test_webhook_verify_bad_token(client):
    r = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "X"})
    assert r.status_code == 403


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_admin_requires_auth(client):
    assert client.get("/api/users").status_code == 401


def test_admin_login_and_crud(client):
    client.post("/admin/login", data={"password": settings.admin_password})
    # add a user
    r = client.post("/api/users", json={
        "flat": "C-101", "whatsapp_number": "918", "entities": {"lights": "light.c101"}})
    assert r.status_code == 200
    flats = [u["flat"] for u in client.get("/api/users").json()]
    assert "C-101" in flats
    # manual device toggle (entity belongs to a registered flat -> allowed)
    r = client.post("/api/device", json={"entity_id": "light.c101", "action": "turn_on"})
    assert r.json()["status"] == "ok"
    # remove
    assert client.delete("/api/users/918").status_code == 200


def test_device_toggle_rejects_unknown_entity(client):
    client.post("/admin/login", data={"password": settings.admin_password})
    client.post("/api/users", json={"flat": "C-1", "whatsapp_number": "917", "entities": {"lights": "light.c1"}})
    # an entity not registered to any flat must be rejected
    r = client.post("/api/device", json={"entity_id": "lock.someone_elses_door", "action": "unlock"})
    assert r.status_code == 403
