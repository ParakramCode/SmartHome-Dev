"""Whapi.Cloud provider: payload parsing, webhook auth, and provider selection."""

import pytest

from smarthome.config import settings
from smarthome.channels import whapi
from smarthome.channels import whatsapp as wa


@pytest.fixture
def use_whapi(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_provider", "whapi")
    monkeypatch.setattr(settings, "whapi_token", "tok_123")
    yield


def test_parse_inbound_text():
    payload = {"messages": [
        {"from": "919", "type": "text", "text": {"body": "AC on"}, "from_me": False},
        {"from": "self", "type": "text", "text": {"body": "echo"}, "from_me": True},  # skipped
    ]}
    assert whapi.parse_inbound(payload) == [{"from": "919", "type": "text", "text": "AC on"}]


def test_parse_inbound_voice():
    payload = {"messages": [
        {"from": "919", "type": "voice", "voice": {"id": "media_1"}, "from_me": False},
    ]}
    msgs = whapi.parse_inbound(payload)
    assert msgs[0]["type"] == "audio" and msgs[0]["audio_id"] == "media_1"


def test_webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "whapi_webhook_secret", "s3cret")
    assert whapi.verify_signature(b"{}", {"X-Whapi-Signature": "s3cret"}) is True
    assert whapi.verify_signature(b"{}", {"Authorization": "Bearer s3cret"}) is True
    assert whapi.verify_signature(b"{}", {"X-Whapi-Signature": "nope"}) is False


def test_webhook_no_secret_allows(monkeypatch):
    monkeypatch.setattr(settings, "whapi_webhook_secret", None)
    assert whapi.verify_signature(b"{}", {}) is True


def test_facade_selects_whapi(use_whapi):
    # The provider-agnostic facade routes to Whapi when configured.
    assert wa.provider_name() == "whapi"
    payload = {"messages": [{"from": "919", "type": "text", "text": {"body": "lights on"}}]}
    assert wa.parse_inbound(payload) == [{"from": "919", "type": "text", "text": "lights on"}]


def test_whapi_enabled_flag(use_whapi):
    assert settings.whatsapp_enabled is True
