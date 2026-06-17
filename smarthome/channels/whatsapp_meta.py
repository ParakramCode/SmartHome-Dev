"""
whatsapp_meta.py — Official WhatsApp Business Cloud API (Meta) provider.

Selected when WHATSAPP_PROVIDER=meta (the default). Token + webhook model:
inbound messages arrive via the signed webhook; outbound goes through the
Graph API. Used behind the provider-agnostic facade in whatsapp.py.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from typing import Mapping

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"


class MetaClient:
    """Minimal WhatsApp Cloud API client."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=GRAPH_API,
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            timeout=15.0,
        )
        self._phone_id = settings.whatsapp_phone_number_id

    async def send_text(self, to: str, body: str) -> bool:
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
            logger.error("Meta send failed %d: %s", resp.status_code, resp.text[:300])
            return False
        except Exception as exc:
            logger.exception("Meta send error: %s", exc)
            return False

    async def download_media(self, media_id: str) -> bytes | None:
        try:
            meta = await self._client.get(f"/{media_id}")
            if meta.status_code != 200:
                return None
            url = meta.json().get("url")
            if not url:
                return None
            resp = await self._client.get(url)
            return resp.content if resp.status_code == 200 else None
        except Exception as exc:
            logger.exception("Meta media download error: %s", exc)
            return None

    async def close(self) -> None:
        await self._client.aclose()


def make_client() -> MetaClient:
    return MetaClient()


def verify_signature(payload: bytes, headers: Mapping[str, str]) -> bool:
    """Verify Meta's X-Hub-Signature-256 header (HMAC-SHA256 of the raw body)."""
    if not settings.whatsapp_app_secret:
        logger.warning("WHATSAPP_APP_SECRET unset — skipping signature check.")
        return True
    header = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Meta's GET verification handshake. Returns the challenge if valid."""
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return challenge
    return None


def parse_inbound(payload: dict) -> list[dict]:
    """Flatten a Meta webhook payload into [{from, type, text|audio_id}]."""
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
