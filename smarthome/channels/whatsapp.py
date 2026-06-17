"""
whatsapp.py — Provider-agnostic WhatsApp channel.

Picks the active provider (Meta official, or Whapi.Cloud unofficial) from
settings.whatsapp_provider and exposes one interface to the rest of the app:
the web layer calls verify_signature/verify_webhook/parse_inbound, and the
WhatsAppChannel runs inbound messages through the shared dispatcher. Swapping
providers is a single env var; nothing else changes.
"""

from __future__ import annotations

import logging
from typing import Mapping

from ..config import settings
from ..core import Dispatcher
from . import whatsapp_meta as meta
from . import whapi as whapi

logger = logging.getLogger(__name__)


def _provider():
    return whapi if settings.whatsapp_provider == "whapi" else meta


def provider_name() -> str:
    return "whapi" if settings.whatsapp_provider == "whapi" else "meta"


def make_client():
    return _provider().make_client()


# --- delegated webhook helpers (used by the web layer) ---
def verify_signature(payload: bytes, headers: Mapping[str, str]) -> bool:
    return _provider().verify_signature(payload, headers)


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    return _provider().verify_webhook(mode, token, challenge)


def parse_inbound(payload: dict) -> list[dict]:
    return _provider().parse_inbound(payload)


class WhatsAppChannel:
    """Glue between the active WhatsApp provider and the shared dispatcher."""

    def __init__(self, dispatcher: Dispatcher, client=None):
        self.dispatcher = dispatcher
        self.client = client or make_client()
        # Set by the voice feature when enabled: async (audio_id) -> str | None
        self.transcribe = None
        logger.info("WhatsApp channel using provider: %s", provider_name())

    async def process(self, payload: dict) -> None:
        """Process all messages in a webhook payload, replying to each sender."""
        for msg in parse_inbound(payload):
            sender = msg.get("from")
            if not sender:
                continue

            text = msg.get("text")
            if msg.get("type") == "audio":
                if self.transcribe and msg.get("audio_id"):
                    text = await self.transcribe(msg["audio_id"])
                if not text:
                    await self.client.send_text(
                        sender, "I couldn't process that voice note. Please type your command."
                    )
                    continue

            async def notify(body: str, _to=sender) -> None:
                await self.client.send_text(_to, body)

            try:
                reply = await self.dispatcher.handle(
                    channel="whatsapp", message=text or "", whatsapp_number=sender, notify=notify,
                )
            except Exception:
                logger.exception("Dispatcher error handling WhatsApp message")
                reply = "Something went wrong. Please try again in a moment."
            await self.client.send_text(sender, reply or "Something went wrong. Please try again.")
