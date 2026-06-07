"""
ha_client.py — Home Assistant REST API client.

Async client using httpx to control smart home devices via
the Home Assistant API. Every method returns a result gracefully
and never raises — errors are logged and False/None is returned.
"""

import logging
import httpx

from config import ENV

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HA_BASE_URL: str = ENV["HA_BASE_URL"].rstrip("/")
HA_TOKEN: str = ENV["HA_TOKEN"]
TIMEOUT: float = 10.0


class HomeAssistantClient:
    """Async client for the Home Assistant REST API."""

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(
            base_url=HA_BASE_URL,
            headers=self._headers,
            timeout=TIMEOUT,
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

        logger.info("HA request  -> %s %s  payload=%s", "POST", url, payload)

        try:
            response = await self._client.post(url, json=payload)
            logger.info(
                "HA response <- %s %s  status=%d",
                "POST", url, response.status_code,
            )

            if response.status_code in (200, 201):
                return True

            logger.error(
                "HA unexpected status %d — body: %s",
                response.status_code,
                response.text[:500],
            )
            return False

        except httpx.TimeoutException:
            logger.error("HA request timed out: %s %s", "POST", url)
            return False
        except httpx.ConnectError:
            logger.error("HA connection refused — is Home Assistant running at %s?", HA_BASE_URL)
            return False
        except Exception as exc:
            logger.exception("HA unexpected error calling %s: %s", url, exc)
            return False

    # ------------------------------------------------------------------
    # Public API — device control
    # ------------------------------------------------------------------
    async def turn_on(self, entity_id: str) -> bool:
        """Turn on a device (switch, light, climate, etc.)."""
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_on", entity_id)

    async def turn_off(self, entity_id: str) -> bool:
        """Turn off a device."""
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_off", entity_id)

    async def lock(self, entity_id: str) -> bool:
        """Lock a lock entity."""
        return await self._call_service("lock", "lock", entity_id)

    async def unlock(self, entity_id: str) -> bool:
        """Unlock a lock entity."""
        return await self._call_service("lock", "unlock", entity_id)

    async def set_temperature(self, entity_id: str, temp: float) -> bool:
        """Set target temperature on a climate entity."""
        return await self._call_service(
            "climate", "set_temperature", entity_id, temperature=temp
        )

    # ------------------------------------------------------------------
    # Public API — state queries
    # ------------------------------------------------------------------
    async def get_state(self, entity_id: str) -> str | None:
        """Get the current state string of an entity. Returns None on error."""
        url = f"/api/states/{entity_id}"
        logger.info("HA request  -> GET %s", url)

        try:
            response = await self._client.get(url)
            logger.info("HA response <- GET %s  status=%d", url, response.status_code)

            if response.status_code == 200:
                data = response.json()
                state = data.get("state", "unknown")
                logger.info("HA state of %s = %s", entity_id, state)
                return state

            logger.error(
                "HA unexpected status %d for state query — body: %s",
                response.status_code,
                response.text[:500],
            )
            return None

        except httpx.TimeoutException:
            logger.error("HA state query timed out: GET %s", url)
            return None
        except httpx.ConnectError:
            logger.error("HA connection refused — is Home Assistant running at %s?", HA_BASE_URL)
            return None
        except Exception as exc:
            logger.exception("HA unexpected error querying %s: %s", url, exc)
            return None

    async def get_all_states(self) -> list:
        """Get all entity states. Returns empty list on error."""
        url = "/api/states"
        logger.info("HA request  -> GET %s", url)

        try:
            response = await self._client.get(url)
            logger.info("HA response <- GET %s  status=%d", url, response.status_code)

            if response.status_code == 200:
                return response.json()

            logger.error(
                "HA unexpected status %d for all-states query — body: %s",
                response.status_code,
                response.text[:500],
            )
            return []

        except httpx.TimeoutException:
            logger.error("HA all-states query timed out")
            return []
        except httpx.ConnectError:
            logger.error("HA connection refused — is Home Assistant running at %s?", HA_BASE_URL)
            return []
        except Exception as exc:
            logger.exception("HA unexpected error querying all states: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
