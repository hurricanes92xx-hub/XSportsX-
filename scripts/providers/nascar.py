#!/usr/bin/env python3
"""Official NASCAR schedule provider.

The feed.nascar.com API is the primary source. The provider requests the
season schedule once per series, then normalizes practice, qualifying and race
runs into the same canonical event shape used by the rest of XSportsX.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://feed.nascar.com"
HEADERS = {"User-Agent": "XSportsX-Schedule/3.0", "Accept": "application/json"}
SERIES = {
    "NASCAR Cup": 1,
    "NASCAR Xfinity": 2,
    "NASCAR Truck": 3,
}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read())


def _parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _normalize(item, league):
    start = _parse(item.get("start_time_utc") or item.get("start_time"))
    if not start:
        return None
    run_type = int(item.get("run_type") or 3)
    run_name = {1: "Practice", 2: "Qualifying", 3: "Race"}.get(run_type, "Session")
    race_name = str(item.get("race_name") or item.get("event_name") or league).strip()
    track = str(item.get("track_name") or "").strip()
    title = f"{race_name} — {run_name}"
    if track:
        title += f" @ {track}"
    event = {
        "league": league,
        "title": title,
        "start": start.isoformat().replace("+00:00", "Z"),
        "tag": "UPCOMING" if start > datetime.now(timezone.utc) else "FINAL",
        "icon": "🏎️",
        "source": "nascar",
    }
    race_id = item.get("race_id")
    if race_id is not None:
        event["providerEventId"] = f"nascar:{race_id}:{run_type}:{start.strftime('%Y%m%d%H%M')}"
    return event


def _extract(root):
    if isinstance(root, list):
        return root
    if isinstance(root, dict):
        for key in ("weekends", "schedule", "data", "results", "items"):
            value = root.get(key)
            if isinstance(value, list):
                return value
    return []


def fetch_league(league, season=None, horizon_days=370):
    series_id = SERIES.get(league)
    if not series_id:
        return []
    year = int(season or datetime.now(timezone.utc).year)
    params = urllib.parse.urlencode({"series_id": series_id, "race_season": year, "v": "1"})
    url = f"{BASE}/api/weekendschedule?{params}"
    try:
        root = _get(url)
    except Exception as exc:
        print(f"ERROR NASCAR {league}: {exc}")
        return []
    now = datetime.now(timezone.utc) - timedelta(hours=12)
    cutoff = datetime.now(timezone.utc) + timedelta(days=horizon_days)
    events = []
    seen = set()
    for item in _extract(root):
        event = _normalize(item, league)
        if not event:
            continue
        dt = _parse(event["start"])
        if not dt or dt < now or dt > cutoff:
            continue
        key = (event["league"], event["title"], event["start"])
        if key not in seen:
            seen.add(key)
            events.append(event)
    return events
