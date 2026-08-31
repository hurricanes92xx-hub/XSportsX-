#!/usr/bin/env python3
"""Resilient schedule wrapper.

Keeps the existing canonical publisher, but replaces known-broken provider paths
with stable season-level APIs.  In particular:
- NASCAR Xfinity/Truck use NASCAR's schedule feed instead of HTML scraping.
- NCAA 2026+ schedules use the GraphQL-backed schedule-alt endpoint instead of
  the discontinued daily scoreboard path.
- The generic fallback parser tolerates the nested payload shapes used by those APIs.
"""
from __future__ import annotations

import importlib.util
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

refresh = load("xsportsx_refresh_resilient", ROOT / "scripts" / "refresh_schedules.py")

HEADERS = {
    **getattr(refresh, "HEADERS", {}),
    "User-Agent": "XSportsX-Schedule/3.0 (+schedule-resilient)",
    "Accept": "application/json, text/plain, */*",
}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()

refresh.get = get


def iso(value):
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00"), text.replace("z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate).astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d%I:%M%p", "%Y-%m-%d%H:%M", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def team_name(team):
    if not isinstance(team, dict):
        return ""
    names = team.get("names") if isinstance(team.get("names"), dict) else team
    return str(names.get("short") or names.get("displayName") or names.get("full") or names.get("name") or "").strip()


def add_ncaa_resilient(events, name, sport, division, icon, days=30):
    """Use the 2026+ NCAA GraphQL-backed schedule endpoint once per sport."""
    year = datetime.now(timezone.utc).year
    url = f"https://ncaa-api.henrygd.me/schedule-alt/{sport}/{division}/{year}"
    try:
        root = json.loads(get(url).decode("utf-8"))
    except Exception as exc:
        print(f"ERROR NCAA resilient {name}: {exc}")
        return False, 0

    now = datetime.now(timezone.utc) - timedelta(hours=12)
    horizon = datetime.now(timezone.utc) + timedelta(days=max(days, 180))
    added = 0
    seen = {(e.get("league"), e.get("title"), e.get("start")) for e in events}

    for obj in walk(root):
        date = obj.get("startDate") or obj.get("date") or obj.get("gameDate")
        raw_time = obj.get("startTime") or obj.get("time") or obj.get("startDateTime")
        dt = iso(raw_time) if raw_time and ("T" in str(raw_time) or ":" in str(raw_time)) else None
        if not dt and date:
            d = str(date).strip()
            t = str(raw_time or "").strip().replace("ET", "")
            for fmt in ("%Y-%m-%d%I:%M%p", "%Y-%m-%d%H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(d + t, fmt).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
                    break
                except ValueError:
                    continue
        if not dt or dt < now or dt > horizon:
            continue

        away = team_name(obj.get("away") or obj.get("awayTeam"))
        home = team_name(obj.get("home") or obj.get("homeTeam"))
        title = str(obj.get("title") or obj.get("name") or "").strip()
        if away and home:
            title = f"{away} @ {home}"
        if not title:
            continue

        key = (name, title, dt.isoformat())
        if key in seen:
            continue
        seen.add(key)
        state = str(obj.get("gameState") or obj.get("status") or "").lower()
        tag = "LIVE" if any(x in state for x in ("live", "progress", "in-progress")) else ("FINAL" if state in ("f", "final", "complete") else "UPCOMING")
        events.append({"league": name, "title": title, "start": dt.isoformat().replace("+00:00", "Z"), "tag": tag, "icon": icon, "source": "ncaa-schedule-alt"})
        added += 1

    print(f"NCAA resilient {name}: {added} events from schedule-alt")
    return True, added


def add_nascar_series(events, name, wanted):
    """Use NASCAR's machine-readable season/weekend schedule feed."""
    url = "https://feed.nascar.com/api/weekendschedule"
    try:
        root = json.loads(get(url).decode("utf-8"))
    except Exception as exc:
        print(f"ERROR NASCAR resilient {name}: {exc}")
        return False, 0

    now = datetime.now(timezone.utc) - timedelta(hours=12)
    horizon = datetime.now(timezone.utc) + timedelta(days=370)
    added = 0
    seen = {(e.get("league"), e.get("title"), e.get("start")) for e in events}
    # NASCAR's feed has historically used 1/2/3 for Cup/Xfinity/Truck.  Text
    # matching is preferred when the payload exposes series names.
    ids = {"cup": {1}, "xfinity": {2}, "truck": {3}}

    for obj in walk(root):
        if not isinstance(obj, dict):
            continue
        sid = obj.get("series_id") or obj.get("seriesId")
        series_text = " ".join(str(obj.get(k) or "") for k in ("series_name", "seriesName", "series", "series_alias")).lower()
        match = False
        if wanted == "xfinity":
            match = "xfinity" in series_text or "o'reilly" in series_text or "oreilly" in series_text or sid in ids["xfinity"]
        elif wanted == "truck":
            match = "truck" in series_text or "craftsman" in series_text or sid in ids["truck"]
        else:
            match = "cup" in series_text or "premier" in series_text or sid in ids["cup"]
        if not match:
            continue

        raw = obj.get("start_time_utc") or obj.get("startTimeUtc") or obj.get("start_time") or obj.get("startTime")
        dt = iso(raw)
        if not dt or dt < now or dt > horizon:
            continue
        event_name = str(obj.get("event_name") or obj.get("eventName") or obj.get("race_name") or obj.get("raceName") or "NASCAR event").strip()
        track = str(obj.get("track_name") or obj.get("trackName") or "").strip()
        title = f"{event_name} — {track}" if track and track.lower() not in event_name.lower() else event_name
        key = (name, title, dt.isoformat())
        if key in seen:
            continue
        seen.add(key)
        run_type = obj.get("run_type") or obj.get("runType")
        tag = "UPCOMING" if str(run_type) != "3" else "UPCOMING"
        events.append({"league": name, "title": title, "start": dt.isoformat().replace("+00:00", "Z"), "tag": tag, "icon": "🏎️", "source": "nascar-feed"})
        added += 1

    print(f"NASCAR resilient {name}: {added} events from feed.nascar.com")
    return True, added


_original_official = refresh.add_official_source
_original_ncaa = refresh.add_ncaa


def add_official_source_resilient(events, source):
    name = str(source.get("league") or "").strip()
    if name == "NASCAR Xfinity":
        return add_nascar_series(events, name, "xfinity")
    if name == "NASCAR Truck":
        return add_nascar_series(events, name, "truck")
    return _original_official(events, source)


def add_ncaa_resilient_wrapper(events, name, sport, division, icon, days=30):
    # 2026+ uses the GraphQL-backed schedule-alt source. If it returns nothing,
    # fall back to the existing scoreboard implementation for live-day recovery.
    ok, count = add_ncaa_resilient(events, name, sport, division, icon, days)
    if ok and count:
        return ok, count
    try:
        return _original_ncaa(events, name, sport, division, icon, days)
    except Exception as exc:
        print(f"ERROR NCAA legacy fallback {name}: {exc}")
        return False, 0

refresh.add_official_source = add_official_source_resilient
refresh.add_ncaa = add_ncaa_resilient_wrapper

if __name__ == "__main__":
    refresh.main()
