#!/usr/bin/env python3
"""Reconcile current live/final status from ESPN without rebuilding the schedule."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
HEADERS = {"User-Agent": "XSportsX-LiveStatus/2.0", "Accept": "application/json"}
REQUEST_TIMEOUT = 12
RETRIES = 3
START_TOLERANCE_SECONDS = 20 * 60

ESPN_LEAGUES = [
    ("NFL", "football", "nfl"), ("NCAA FB", "football", "college-football"), ("CFL", "football", "cfl"),
    ("NBA", "basketball", "nba"), ("WNBA", "basketball", "wnba"), ("NHL", "hockey", "nhl"),
    ("MLB", "baseball", "mlb"), ("MLS", "soccer", "usa.1"), ("NCAA Men Soccer", "soccer", "usa.ncaa.m.1"),
    ("NCAA Women Soccer", "soccer", "usa.ncaa.w.1"), ("EPL", "soccer", "eng.1"), ("UCL", "soccer", "uefa.champions"),
    ("LaLiga", "soccer", "esp.1"), ("Serie A", "soccer", "ita.1"), ("Bundesliga", "soccer", "ger.1"),
    ("Ligue 1", "soccer", "fra.1"), ("UFC", "mma", "ufc"), ("F1", "racing", "f1"),
    ("IndyCar", "racing", "irl"), ("NASCAR Cup", "racing", "nascar-premier"), ("PGA", "golf", "pga"),
    ("LPGA", "golf", "lpga"), ("LIV Golf", "golf", "liv"), ("ATP", "tennis", "atp"),
    ("WTA", "tennis", "wta"), ("PLL", "lacrosse", "pll"), ("NLL", "lacrosse", "nll"),
    ("FIVB Men", "volleyball", "fivb.m"), ("FIVB Women", "volleyball", "fivb.w"), ("NRL", "rugby-league", "3"),
    ("AFL", "australian-football", "afl"), ("ICC T20", "cricket", "icc.t20"), ("IPL", "cricket", "ipl"),
]


def get_json(url: str):
    urls = [url]
    if "site.api.espn.com" in url:
        urls.append(url.replace("site.api.espn.com", "site.web.api.espn.com"))
    last_error = None
    for endpoint in urls:
        for attempt in range(1, RETRIES + 1):
            try:
                request = urllib.request.Request(endpoint, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    return json.loads(response.read().decode("utf-8", "ignore"))
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < RETRIES:
                    time.sleep(attempt * 2)
    raise RuntimeError(str(last_error))


def iso(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def norm(value: str) -> str:
    value = str(value or "").lower().replace("&", " and ")
    value = re.sub(r"\b(at|vs\.?|versus)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def title_parts(value: str) -> set[str]:
    return {token for token in norm(value).split() if len(token) >= 3}


def espn_title(event: dict, league: str) -> str:
    comp = (event.get("competitions") or [{}])[0]
    teams = comp.get("competitors") or []
    home = next((x.get("team", {}).get("shortDisplayName") or x.get("team", {}).get("displayName") for x in teams if x.get("homeAway") == "home"), "")
    away = next((x.get("team", {}).get("shortDisplayName") or x.get("team", {}).get("displayName") for x in teams if x.get("homeAway") == "away"), "")
    return f"{away} @ {home}" if home and away else str(event.get("name") or event.get("shortName") or league)


def state_tag(event: dict) -> str:
    comp = (event.get("competitions") or [{}])[0]
    status = ((comp.get("status") or {}).get("type") or {})
    if not status:
        status = ((event.get("status") or {}).get("type") or {})
    state = str(status.get("state") or "pre").lower()
    if state == "in":
        return "LIVE"
    if state == "post":
        return "FINAL"
    return "UPCOMING"


def find_match(events: list[dict], league: str, title: str, start: str) -> dict | None:
    remote_time = iso(start)
    remote_tokens = title_parts(title)
    candidates = []
    for event in events:
        if event.get("league") != league:
            continue
        local_time = iso(event.get("start"))
        if remote_time and local_time:
            if abs((local_time - remote_time).total_seconds()) > START_TOLERANCE_SECONDS:
                continue
        elif local_time != remote_time:
            continue
        shared = len(remote_tokens & title_parts(event.get("title") or ""))
        if shared:
            distance = abs((local_time - remote_time).total_seconds()) if remote_time and local_time else 10**9
            candidates.append((shared, distance, event))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def main() -> int:
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    changed = 0
    added_live = 0
    failures: list[str] = []
    today = datetime.now(timezone.utc).date()

    for league, sport, slug in ESPN_LEAGUES:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={today:%Y%m%d}&limit=1000"
        try:
            root = get_json(url)
        except Exception as exc:
            failures.append(f"{league}: {exc}")
            print(f"::warning::LIVE RECONCILE {league}: request failed after retries: {exc}")
            continue

        remote_events = root.get("events") or []
        print(f"LIVE RECONCILE: {league}: scoreboard_events={len(remote_events)}")
        for remote in remote_events:
            start_dt = iso(remote.get("date"))
            if not start_dt:
                continue
            start = start_dt.isoformat().replace("+00:00", "Z")
            title = espn_title(remote, league)
            tag = state_tag(remote)
            event = find_match(events, league, title, start)
            if event is not None:
                if event.get("tag") != tag:
                    event["tag"] = tag
                    event["sourceDetail"] = "ESPN live-status reconciliation"
                    changed += 1
                continue
            if tag == "LIVE":
                events.append({"league": league, "title": title, "start": start, "tag": "LIVE", "icon": "•", "source": "espn", "sourceDetail": "ESPN live-status reconciliation"})
                added_live += 1
                print(f"LIVE RECONCILE: added missing LIVE event: {league} / {title}")

    payload["events"] = events
    payload["eventCounts"] = {k: sum(1 for e in events if e.get("league") == k) for k in sorted({e.get("league") for e in events if e.get("league")})}
    if changed or added_live:
        payload.setdefault("repairReport", {})["liveStatusReconciled"] = changed
        payload["repairReport"]["liveEventsAdded"] = added_live
        payload["repairReport"]["liveReconcileAt"] = datetime.now(timezone.utc).isoformat()
        FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"LIVE RECONCILE: status_updates={changed}; live_events_added={added_live}; scoreboard_failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
