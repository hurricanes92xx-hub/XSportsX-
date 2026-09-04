#!/usr/bin/env python3
"""NASCAR schedule provider using public NASCAR cache with ESPN recovery."""
import json
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://cf.nascar.com/cacher"
HEADERS = {"User-Agent": "XSportsX-Schedule/4.1", "Accept": "application/json"}
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/racing/nascar-premier/scoreboard"
SERIES = {"NASCAR Cup": 1, "NASCAR Xfinity": 2, "NASCAR Truck": 3}


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def _parse(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _normalize(item, league, fallback_race_id=None):
    if not isinstance(item, dict):
        return None
    start = _parse(item.get("start_time_utc") or item.get("start_time") or item.get("race_date") or item.get("date_scheduled"))
    if not start:
        return None
    run_type = int(item.get("run_type") or 3)
    if run_type == 0:
        return None
    run_name = {1: "Practice", 2: "Qualifying", 3: "Race"}.get(run_type, "Session")
    race_name = str(item.get("race_name") or item.get("event_name") or league).strip()
    track = str(item.get("track_name") or "").strip()
    title = f"{race_name} — {run_name}"
    if track:
        title += f" @ {track}"
    event = {"league": league, "title": title, "start": start.isoformat().replace("+00:00", "Z"), "tag": "UPCOMING" if start > datetime.now(timezone.utc) else "FINAL", "icon": "🏎️", "source": "nascar"}
    race_id = item.get("race_id") or fallback_race_id
    if race_id is not None:
        event["providerEventId"] = f"nascar:{race_id}:{run_type}:{start.strftime('%Y%m%d%H%M')}"
    return event


def _series_items(root, series_id):
    if not isinstance(root, dict):
        return []
    if series_id == 1:
        value = root.get("races") or root.get("schedule") or root.get("series_1") or []
        return value if isinstance(value, list) else []
    value = root.get(f"series_{series_id}") or []
    return value if isinstance(value, list) else []


def _race_sessions(race):
    if not isinstance(race, dict):
        return []
    for key in ("schedule", "weekend_schedule", "sessions"):
        value = race.get(key)
        if isinstance(value, list):
            return value
    return [race]


def _espn_cup(horizon_days):
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=horizon_days)
    start = now.date(); end = cutoff.date()
    url = f"{ESPN_URL}?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=1000"
    try:
        root = _get(url, timeout=8)
    except Exception as exc:
        print(f"ERROR NASCAR Cup ESPN recovery: {exc}")
        return []
    out = []
    for event in root.get("events") or []:
        dt = _parse(event.get("date"))
        if not dt or dt < now - timedelta(hours=12) or dt > cutoff:
            continue
        comp = (event.get("competitions") or [{}])[0]
        status = str(((comp.get("status") or {}).get("type") or {}).get("state") or "pre").lower()
        name = str(event.get("name") or event.get("shortName") or "NASCAR Cup").strip()
        event_row = {"league":"NASCAR Cup","title":name,"start":dt.isoformat().replace("+00:00","Z"),"tag":"LIVE" if status=="in" else "FINAL" if status=="post" else "UPCOMING","icon":"🏎️","source":"espn-nascar","providerEventId":f"espn:{event['id']}" if event.get("id") else f"espn:{name}-{dt.isoformat()}"}
        out.append(event_row)
    return out


def fetch_league(league, season=None, horizon_days=370):
    series_id = SERIES.get(league)
    if not series_id:
        return []
    year = int(season or datetime.now(timezone.utc).year)
    urls = [f"{BASE}/{year}/{series_id}/race_list_basic.json" if series_id == 1 else f"{BASE}/{year}/race_list_basic.json"]
    root = None
    last_error = None
    for url in urls:
        try:
            root = _get(url)
            break
        except Exception as exc:
            last_error = exc
    if root is None:
        print(f"ERROR NASCAR {league}: {last_error}")
        return _espn_cup(horizon_days) if league == "NASCAR Cup" else []
    now = datetime.now(timezone.utc) - timedelta(hours=12)
    cutoff = datetime.now(timezone.utc) + timedelta(days=horizon_days)
    events = []
    seen = set()
    for race in _series_items(root, series_id):
        race_id = race.get("race_id") if isinstance(race, dict) else None
        for session in _race_sessions(race):
            item = dict(session) if isinstance(session, dict) else {}
            for key in ("race_id", "race_name", "track_name"):
                if key not in item and isinstance(race, dict) and race.get(key) is not None:
                    item[key] = race[key]
            event = _normalize(item, league, race_id)
            if not event:
                continue
            dt = _parse(event["start"])
            if not dt or dt < now or dt > cutoff:
                continue
            key = (event["league"], event["title"], event["start"])
            if key not in seen:
                seen.add(key)
                events.append(event)
    if league == "NASCAR Cup" and not events:
        events = _espn_cup(horizon_days)
        if events:
            print(f"REPAIRED NASCAR Cup via ESPN recovery: {len(events)} events")
    return events
