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
    monkeypatch.setattr(settings, "whatsapp_app_secret", "topsecret")
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert wa.verify_signature(body, sig) is True
    assert wa.verify_signature(body, "sha256=deadbeef") is False


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
    # manual device toggle
    r = client.post("/api/device", json={"entity_id": "light.c101", "action": "turn_on"})
    assert r.json()["status"] == "ok"
    # remove
    assert client.delete("/api/users/918").status_code == 200
