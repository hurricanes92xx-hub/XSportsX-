#!/usr/bin/env python3
"""Shared scheduling engine primitives for XSportsX.

The publisher can use these helpers to prevent source overload while preserving
fresh data: priority queues, per-source token buckets, exponential backoff,
circuit breakers, and tiered TTLs.
"""
from __future__ import annotations

import heapq
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
    """Bounded priority queue; lower priority number runs first."""
    def __init__(self, max_queue: int = 2000):
        self.max_queue = max_queue
        self._queue: list[ScheduleJob] = []

    def submit(self, job: ScheduleJob) -> bool:
        if len(self._queue) >= self.max_queue:
            return False
        heapq.heappush(self._queue, job)
        return True

    def pop_ready(self, now: float | None = None) -> ScheduleJob | None:
        now = time.monotonic() if now is None else now
        if self._queue and self._queue[0].run_at <= now:
            return heapq.heappop(self._queue)
        return None

    def __len__(self) -> int:
        return len(self._queue)


class TokenBucket:
    def __init__(self, rate_per_second: float, burst: int):
        self.rate = max(rate_per_second, 0.001)
        self.capacity = max(burst, 1)
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now
        if self.tokens < cost:
            return False
        self.tokens -= cost
        return True


@dataclass
class Circuit:
    failures: int = 0
    opened_until: float = 0.0
    threshold: int = 4
    cooldown: float = 300.0

    def available(self) -> bool:
        return time.monotonic() >= self.opened_until

    def success(self) -> None:
        self.failures = 0
        self.opened_until = 0.0

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_until = time.monotonic() + self.cooldown


class SourceGuard:
    """Per-source throttling and circuit-breaker state."""
    def __init__(self, rate_per_second: float = 2.0, burst: int = 4):
        self.bucket = TokenBucket(rate_per_second, burst)
        self.circuit = Circuit()

    def can_request(self) -> bool:
        return self.circuit.available() and self.bucket.allow()

    def ok(self) -> None:
        self.circuit.success()

    def failed(self) -> None:
        self.circuit.failure()


def backoff_seconds(attempt: int, base: float = 30.0, maximum: float = 1800.0) -> float:
    """Exponential backoff with a deterministic cap."""
    return min(maximum, base * (2 ** max(0, attempt - 1)))


# Refresh tiers are deliberately conservative for a large multi-sport catalog.
TTL_SECONDS = {
    "live": 15,
    "today": 60,
    "next_3_days": 300,
    "next_30_days": 21600,
    "long_range": 43200,
    "metadata": 86400,
}

PRIORITY = {
    "live": 0,
    "today": 1,
    "next_3_days": 2,
    "next_30_days": 3,
    "long_range": 4,
    "metadata": 5,
}
