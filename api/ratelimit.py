"""Limite de tasa simple por IP, en memoria."""

from __future__ import annotations

import os
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = max(1, per_minute)
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def limiter_from_env() -> RateLimiter:
    try:
        per_minute = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
    except ValueError:
        per_minute = 30
    return RateLimiter(per_minute)
