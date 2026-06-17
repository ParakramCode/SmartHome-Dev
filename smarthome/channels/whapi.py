"""
whapi.py — Whapi.Cloud (unofficial WhatsApp gateway) provider.

Selected when WHATSAPP_PROVIDER=whapi. Whapi runs a real WhatsApp account
(linked via QR in the Whapi panel) and exposes a simple token + webhook REST
API — no Meta business verification or message templates required.

Trade-off: unofficial (WhatsApp Web automation), so the linked number can be
banned. Good for fast pilots; keep the Meta provider for compliant scale.
Used behind the provider-agnostic facade in whatsapp.py.

API model (https://whapi.readme.io):
  - send text : POST {WHAPI_API_URL}/messages/text  {"to": "<number>", "body": "<text>"}
  - download  : GET  {WHAPI_API_URL}/media/{id}
  - inbound   : webhook POSTs {"messages": [ {from, type, text:{body}, from_me, ...} ]}
"""

from __future__ import annotations

import hmac
import logging
from typing import Mapping

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class WhapiClient:
    """Minimal Whapi.Cloud client."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.whapi_api_url,
            headers={"Authorization": f"Bearer {settings.whapi_token}"},
            timeout=15.0,
        )

    async def send_text(self, to: str, body: str) -> bool:
        try:
            resp = await self._client.post(
                "/messages/text", json={"to": to, "body": body[:4096]}
            )
            if resp.status_code in (200, 201):
                # Whapi returns {"sent": true, ...} on success.
                return bool(resp.json().get("sent", True))
            logger.error("Whapi send failed %d: %s", resp.status_code, resp.text[:300])
            return False
        except Exception as exc:
            logger.exception("Whapi send error: %s", exc)
            return False

    async def download_media(self, media_id: str) -> bytes | None:
        try:
            resp = await self._client.get(f"/media/{media_id}")
            return resp.content if resp.status_code == 200 else None
        except Exception as exc:
            logger.exception("Whapi media download error: %s", exc)
            return None

    async def close(self) -> None:
        await self._client.aclose()


def make_client() -> WhapiClient:
    return WhapiClient()


def verify_signature(payload: bytes, headers: Mapping[str, str]) -> bool:
    """Verify the Whapi webhook secret if configured.

    Whapi doesn't sign payloads like Meta; instead you set a secret token in the
    panel and it's sent back on each webhook. If WHAPI_WEBHOOK_SECRET is set we
    require a matching token header; otherwise we allow (and warn).
    """
    secret = settings.whapi_webhook_secret
    if not secret:
        logger.warning("WHAPI_WEBHOOK_SECRET unset — skipping webhook auth check.")
        return True
    provided = (
        headers.get("X-Whapi-Signature")
        or headers.get("x-whapi-signature")
        or headers.get("Authorization")
        or ""
    )
    provided = provided.replace("Bearer ", "").strip()
    return hmac.compare_digest(secret, provided)


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Whapi has no GET verification handshake; this is unused (see app.py)."""
    return challenge


def parse_inbound(payload: dict) -> list[dict]:
    """Flatten a Whapi webhook payload into [{from, type, text|audio_id}].

    Skips our own outgoing messages (from_me) to avoid reply loops.
    """
    out: list[dict] = []
    for msg in payload.get("messages", []):
        if msg.get("from_me"):
            continue
        mtype = msg.get("type")
        item = {"from": msg.get("from"), "type": mtype}
        if mtype == "text":
            item["text"] = msg.get("text", {}).get("body", "")
        elif mtype in ("audio", "voice"):
            item["type"] = "audio"
            media = msg.get(mtype) or {}
            item["audio_id"] = media.get("id")
        out.append(item)
    return out
