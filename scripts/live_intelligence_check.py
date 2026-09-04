#!/usr/bin/env python3
"""30-minute lightweight live-state and source-health pass.

This pass intentionally avoids the full schedule crawl. It focuses on events that
are live or close to live, validates existing source metadata, and researches only
urgent source gaps. The canonical schedule remains authoritative; this script never
invents events or playable URLs.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def safe_url(value: str) -> bool:
    try:
        p = urlparse(value)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def probe(url: str) -> bool:
    if not safe_url(url):
        return False
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "XSportsX-LiveCheck/1.0"})
        with urlopen(req, timeout=4) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except Exception:
        try:
            req = Request(url, method="GET", headers={"User-Agent": "XSportsX-LiveCheck/1.0", "Range": "bytes=0-512"})
            with urlopen(req, timeout=4) as response:
                return 200 <= getattr(response, "status", 200) < 500
        except Exception:
            return False


def main() -> int:
    if not FEED.exists():
        print("LIVE_CHECK: no canonical feed yet")
        return 0

    feed = json.loads(FEED.read_text(encoding="utf-8"))
    events = feed.get("events") or []
    now = now_utc()
    urgent = []
    source_failures = 0
    missing_sources = 0
    live_count = 0

    for event in events:
        start = parse_dt(str(event.get("startUtc", "")))
        if not start:
            continue
        minutes = (start - now).total_seconds() / 60.0
        is_live = bool(event.get("isLive")) or str(event.get("lifecycle", "")).startswith("LIVE") or str(event.get("phase", "")).upper() == "LIVE"
        # Keep the 30-minute pass small: current LIVE + next 30 minutes + recently started events.
        if not is_live and not (-5 <= minutes <= 30):
            continue
        live_count += 1
        source = event.get("sourceUrl") or event.get("streamUrl") or event.get("watchUrl")
        if not source:
            missing_sources += 1
            urgent.append({"id": event.get("id"), "action": "discover_event_source_metadata"})
        elif not probe(str(source)):
            source_failures += 1
            urgent.append({"id": event.get("id"), "action": "probe_live_state_and_source"})

    # Only research urgent missing-source events. Keep the research budget bounded.
    researched = 0
    if urgent:
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from sports_web_research import research_live
            by_id = {str(e.get("id")): e for e in events}
            for item in urgent[:20]:
                event = by_id.get(str(item.get("id")))
                if not event:
                    continue
                result = research_live(event, limit=5)
                item["webResearch"] = result
                researched += 1
        except Exception as exc:
            feed.setdefault("liveCheck", {})["researchError"] = str(exc)[:300]

    stamp = now.isoformat().replace("+00:00", "Z")
    feed["liveCheck"] = {
        "schema": 1,
        "checkedAtUtc": stamp,
        "liveOrUrgentEvents": live_count,
        "missingSources": missing_sources,
        "sourceFailures": source_failures,
        "urgentRepairs": urgent[:20],
        "researchedUrgentSources": researched,
    }
    feed["lastLiveCheckUtc"] = stamp
    FEED.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"LIVE_CHECK: events={live_count} missingSources={missing_sources} sourceFailures={source_failures} researched={researched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
