#!/usr/bin/env python3
"""Run the canonical publisher through bounded, rate-limited source access."""
from __future__ import annotations

import importlib.util
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


refresh = load("xsportsx_refresh", ROOT / "scripts" / "refresh_schedules.py")
engine = load("xsportsx_schedule_engine_safe", ROOT / "scripts" / "schedule_engine_safe.py")

# The underlying publisher has NCAA fan-out and provider fallbacks. Keep a hard
# global ceiling so a large league catalog can never create an unbounded burst.
MAX_CONCURRENT = 8
semaphore = threading.BoundedSemaphore(MAX_CONCURRENT)
guards: dict[str, engine.SourceGuard] = {}
guards_lock = threading.Lock()


def guard_for(url: str) -> engine.SourceGuard:
    host = urllib.parse.urlsplit(url).netloc.lower() or "unknown"
    with guards_lock:
        return guards.setdefault(host, engine.SourceGuard())


def guarded_get(url: str):
    guard = guard_for(url)
    for attempt in range(1, 5):
        guard.wait_turn()
        with semaphore:
            try:
                req = urllib.request.Request(url, headers=refresh.HEADERS)
                with urllib.request.urlopen(req, timeout=12) as response:
                    data = response.read()
                guard.success()
                return data
            except Exception:
                guard.failure()
                if attempt >= 4:
                    raise
                time.sleep(engine.backoff_seconds(attempt))


refresh.get = guarded_get
refresh.main()
