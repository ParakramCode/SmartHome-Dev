"""
whatsapp.py — WhatsApp Business Cloud API channel (production).

Provides:
  - WhatsAppClient: send text messages, download media (for voice notes)
  - signature verification (HMAC-SHA256) for inbound webhooks
  - inbound payload parsing
  - WhatsAppChannel.process(): run inbound messages through the dispatcher

The actual HTTP webhook routes live in smarthome/web/app.py; this module owns
everything WhatsApp-specific so the web layer stays generic.
"""

from __future__ import annotations

import hmac
import hashlib
import logging

import httpx

from ..config import settings
from ..core import Dispatcher

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"


class WhatsAppClient:
    """Minimal WhatsApp Cloud API client."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=GRAPH_API,
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            timeout=15.0,
        )
        self._phone_id = settings.whatsapp_phone_number_id

    async def send_text(self, to: str, body: str) -> bool:
        """Send a text message. WhatsApp caps bodies at 4096 chars."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body[:4096]},
        }
        try:
            resp = await self._client.post(f"/{self._phone_id}/messages", json=payload)
            if resp.status_code == 200:
                return True
            logger.error("WhatsApp send failed %d: %s", resp.status_code, resp.text[:300])
            return False
        except Exception as exc:
            logger.exception("WhatsApp send error: %s", exc)
            return False

    async def download_media(self, media_id: str) -> bytes | None:
        """Fetch media bytes (used by voice-note transcription)."""
        try:
            meta = await self._client.get(f"/{media_id}")
            if meta.status_code != 200:
                return None
            url = meta.json().get("url")
            if not url:
                return None
            # Media URL needs the same bearer token but is on a different host.
            resp = await self._client.get(url)
            return resp.content if resp.status_code == 200 else None
        except Exception as exc:
            logger.exception("WhatsApp media download error: %s", exc)
            return None

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Webhook helpers
# ---------------------------------------------------------------------------
def verify_signature(payload: bytes, header: str | None) -> bool:
    """Verify Meta's X-Hub-Signature-256 header (HMAC-SHA256 of the raw body)."""
    if not settings.whatsapp_app_secret:
        # No secret configured -> can't verify. Allow in dev, warn loudly.
        logger.warning("WHATSAPP_APP_SECRET unset — skipping signature check.")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    provided = header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Handle Meta's GET verification handshake. Returns the challenge if valid."""
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return challenge
    return None


def parse_inbound(payload: dict) -> list[dict]:
    """Flatten a webhook payload into [{from, type, text|audio_id}] messages."""
    out: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                mtype = msg.get("type")
                item = {"from": msg.get("from"), "type": mtype}
                if mtype == "text":
                    item["text"] = msg.get("text", {}).get("body", "")
                elif mtype == "audio":
                    item["audio_id"] = msg.get("audio", {}).get("id")
                out.append(item)
    return out


class WhatsAppChannel:
    """Glue between the WhatsApp client and the shared dispatcher."""

    def __init__(self, dispatcher: Dispatcher, client: WhatsAppClient | None = None):
        self.dispatcher = dispatcher
        self.client = client or WhatsAppClient()
        # Set by the voice feature when enabled: async (audio_id) -> str | None
        self.transcribe = None

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

            reply = await self.dispatcher.handle(
                channel="whatsapp", message=text or "", whatsapp_number=sender, notify=notify,
            )
            await self.client.send_text(sender, reply)
