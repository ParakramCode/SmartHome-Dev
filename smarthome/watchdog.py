"""
watchdog.py — Home Assistant reliability monitor.

Periodically pings Home Assistant. On a healthy -> down transition it:
  1. alerts the admin (via the provided notify callback, e.g. WhatsApp), and
  2. optionally runs HA_RESTART_CMD to restart the service.
On recovery (down -> up) it sends an all-clear. State transitions are logged
once (not every tick) to avoid alert spam.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from .config import settings
from .ha_client import HomeAssistantClient
from . import messages

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str], Awaitable[None]]


class Watchdog:
    def __init__(
        self,
        ha: HomeAssistantClient,
        notify_admin: NotifyFn | None = None,
        interval_minutes: int | None = None,
    ):
        self.ha = ha
        self.notify_admin = notify_admin
        self.interval = (interval_minutes or settings.watchdog_interval_minutes) * 60
        self._healthy: bool | None = None  # None = unknown (first run)
        self._task: asyncio.Task | None = None

    async def _restart_ha(self) -> None:
        cmd = settings.ha_restart_cmd
        if not cmd:
            logger.warning("HA down but HA_RESTART_CMD is not set — cannot auto-restart.")
            return
        logger.warning("Attempting HA restart: %s", cmd)
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info("HA restart command succeeded.")
            else:
                logger.error("HA restart failed (%d): %s", proc.returncode, stderr.decode()[:300])
        except Exception as exc:
            logger.exception("HA restart command error: %s", exc)

    async def _alert(self, text: str) -> None:
        if self.notify_admin:
            try:
                await self.notify_admin(text)
            except Exception as exc:
                logger.exception("Watchdog admin alert failed: %s", exc)

    async def _tick(self) -> None:
        up = await self.ha.ping()
        if up and self._healthy is not True:
            if self._healthy is False:  # recovery (skip on first-ever success)
                logger.info("Home Assistant recovered.")
                await self._alert("✅ Home Assistant is back online.")
            self._healthy = True
        elif not up and self._healthy is not False:
            logger.error("Home Assistant is DOWN.")
            self._healthy = False
            await self._alert("🚨 Home Assistant is DOWN. Attempting restart…")
            await self._restart_ha()

    async def run(self) -> None:
        """Run the monitor loop forever (cancel the task to stop)."""
        logger.info("Watchdog started — checking HA every %ds.", self.interval)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Watchdog tick error: %s", exc)
            await asyncio.sleep(self.interval)

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
