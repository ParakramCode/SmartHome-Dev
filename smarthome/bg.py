"""
bg.py — Safe fire-and-forget background tasks.

asyncio does not keep a strong reference to tasks created with create_task(),
so a bare `asyncio.create_task(coro)` can be garbage-collected mid-run. spawn()
keeps a reference until the task finishes and logs any exception (which would
otherwise be swallowed silently).
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def spawn(coro, *, name: str | None = None) -> asyncio.Task:
    """Schedule a coroutine, retaining a reference and logging failures."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        _tasks.discard(t)
        if not t.cancelled():
            exc = t.exception()
            if exc is not None:
                logger.error("Background task %s failed", t.get_name(), exc_info=exc)

    task.add_done_callback(_done)
    return task
