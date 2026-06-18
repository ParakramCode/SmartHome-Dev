"""
ha_client.py — Home Assistant REST API client.

Async client (httpx) for controlling devices and reading state via the
Home Assistant API. Every method degrades gracefully: errors are logged
and a falsy value is returned — methods never raise.
"""

from __future__ import annotations

import logging
import httpx

from .config import settings

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """Async client for the Home Assistant REST API."""

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.ha_token}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=settings.ha_base_url,
            headers=self._headers,
            timeout=settings.ha_timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    async def _call_service(
        self, domain: str, service: str, entity_id: str, **extra_data
    ) -> bool:
        """POST to /api/services/{domain}/{service} with the given entity_id."""
        url = f"/api/services/{domain}/{service}"
        payload = {"entity_id": entity_id, **extra_data}
        logger.info("HA POST %s payload=%s", url, payload)

        try:
            response = await self._client.post(url, json=payload)
            logger.info("HA POST %s -> %d", url, response.status_code)
            if response.status_code in (200, 201):
                return True
            logger.error("HA status %d — body: %s", response.status_code, response.text[:500])
            return False
        except httpx.TimeoutException:
            logger.error("HA request timed out: POST %s", url)
            return False
        except httpx.ConnectError:
            logger.error("HA connection refused — is HA running at %s?", settings.ha_base_url)
            return False
        except Exception as exc:
            logger.exception("HA unexpected error calling %s: %s", url, exc)
            return False

    # ------------------------------------------------------------------
    # Device control
    # ------------------------------------------------------------------
    async def turn_on(self, entity_id: str) -> bool:
        return await self._call_service(entity_id.split(".")[0], "turn_on", entity_id)

    async def turn_off(self, entity_id: str) -> bool:
        return await self._call_service(entity_id.split(".")[0], "turn_off", entity_id)

    async def lock(self, entity_id: str) -> bool:
        return await self._call_service("lock", "lock", entity_id)

    async def unlock(self, entity_id: str) -> bool:
        return await self._call_service("lock", "unlock", entity_id)

    async def set_temperature(self, entity_id: str, temp: float) -> bool:
        return await self._call_service(
            "climate", "set_temperature", entity_id, temperature=temp
        )

    async def set_humidity(self, entity_id: str, pct: int) -> bool:
        return await self._call_service(
            "humidifier", "set_humidity", entity_id, humidity=pct
        )

    async def set_mode(self, entity_id: str, mode: str) -> bool:
        return await self._call_service(
            "humidifier", "set_mode", entity_id, mode=mode
        )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------
    async def get_state(self, entity_id: str) -> str | None:
        """Current state string of an entity, or None on error."""
        url = f"/api/states/{entity_id}"
        try:
            response = await self._client.get(url)
            if response.status_code == 200:
                return response.json().get("state", "unknown")
            logger.error("HA state %d for %s — %s", response.status_code, entity_id, response.text[:300])
            return None
        except httpx.TimeoutException:
            logger.error("HA state query timed out: GET %s", url)
            return None
        except httpx.ConnectError:
            logger.error("HA connection refused — is HA running at %s?", settings.ha_base_url)
            return None
        except Exception as exc:
            logger.exception("HA unexpected error querying %s: %s", url, exc)
            return None

    async def get_attributes(self, entity_id: str) -> dict | None:
        """Full attributes dict of an entity (used by energy reporting), or None."""
        url = f"/api/states/{entity_id}"
        try:
            response = await self._client.get(url)
            if response.status_code == 200:
                return response.json().get("attributes", {})
            return None
        except Exception as exc:
            logger.exception("HA attributes error %s: %s", entity_id, exc)
            return None

    async def ping(self) -> bool:
        """Lightweight reachability check for the watchdog (GET /api/)."""
        try:
            response = await self._client.get("/api/")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
