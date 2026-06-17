"""
ratelimit.py — In-memory per-user sliding-window rate limiter.

Guards against abuse / runaway loops (brief: max 20 commands per user per
minute). In-memory is fine: a single building runs one process, and the limit
is a safety valve, not billing.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from .config import settings


class RateLimiter:
    def __init__(self, max_per_minute: int | None = None, window_seconds: float = 60.0):
        self.max = max_per_minute or settings.rate_limit_per_minute
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record a hit for `key`; return False if it exceeds the window limit."""
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= self.max:
            return False
        hits.append(now)
        return True
