#!/usr/bin/env python3
"""Thread-safe request controls for the XSportsX schedule publisher."""
from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(order=True)
class ScheduleJob:
    priority: int
    run_at: float
    source: str = field(compare=False)
    fn: Callable[[], Any] = field(compare=False)
    attempts: int = field(default=0, compare=False)


class PriorityScheduler:
    def __init__(self, max_queue: int = 2000):
        self.max_queue = max_queue
        self._queue: list[ScheduleJob] = []
        self._lock = threading.Lock()

    def submit(self, job: ScheduleJob) -> bool:
        with self._lock:
            if len(self._queue) >= self.max_queue:
                return False
            heapq.heappush(self._queue, job)
            return True

    def pop_ready(self, now: float | None = None) -> ScheduleJob | None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._queue and self._queue[0].run_at <= now:
                return heapq.heappop(self._queue)
        return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)


class TokenBucket:
    def __init__(self, rate_per_second: float, burst: int):
        self.rate = max(rate_per_second, 0.001)
        self.capacity = max(burst, 1)
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1.0:
                return False
            self.tokens -= 1.0
            return True


class CircuitBreaker:
    def __init__(self, threshold: int = 4, cooldown: float = 300.0):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_until = 0.0
        self._lock = threading.Lock()

    def available(self) -> bool:
        with self._lock:
            return time.monotonic() >= self.opened_until

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_until = 0.0

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_until = time.monotonic() + self.cooldown


class SourceGuard:
    def __init__(self, rate_per_second: float = 1.5, burst: int = 3):
        self.bucket = TokenBucket(rate_per_second, burst)
        self.breaker = CircuitBreaker()

    def wait_turn(self) -> None:
        while self.breaker.available() and not self.bucket.allow():
            time.sleep(0.15)
        if not self.breaker.available():
            raise RuntimeError("source circuit open")

    def success(self) -> None:
        self.breaker.success()

    def failure(self) -> None:
        self.breaker.failure()


def backoff_seconds(attempt: int, base: float = 2.0, maximum: float = 30.0) -> float:
    return min(maximum, base * (2 ** max(0, attempt - 1)))


TTL_SECONDS = {
    "live": 15,
    "today": 60,
    "next_3_days": 300,
    "next_30_days": 21600,
    "long_range": 43200,
    "metadata": 86400,
}
