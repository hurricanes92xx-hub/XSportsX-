#!/usr/bin/env python3
"""Reconcile current live/final status from ESPN without rebuilding the schedule."""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
HEADERS = {
    "User-Agent": "XSportsX-LiveStatus/1.1",
    "Accept": "application/json",
}

# ESPN-backed leagues. Keep this list broad so Live Center is not accidentally
# limited to the handful of major U.S. leagues.
ESPN_LEAGUES = [
    ("NFL", "football", "nfl"),
    ("NCAA FB", "football", "college-football"),
    ("CFL", "football", "cfl"),
    ("NBA", "basketball", "nba"),
    ("WNBA", "basketball", "wnba"),
    ("NHL", "hockey", "nhl"),
    ("MLB", "baseball", "mlb"),
    ("MLS", "soccer", "usa.1"),
    ("NCAA Men Soccer", "soccer", "usa.ncaa.m.1"),
    ("NCAA Women Soccer", "soccer", "usa.ncaa.w.1"),
    ("EPL", "soccer", "eng.1"),
    ("UCL", "soccer", "uefa.champions"),
    ("LaLiga", "soccer", "esp.1"),
    ("Serie A", "soccer", "ita.1"),
    ("Bundesliga", "soccer", "ger.1"),
    ("Ligue 1", "soccer", "fra.1"),
    ("UFC", "mma", "ufc"),
    ("F1", "racing", "f1"),
    ("IndyCar", "racing", "irl"),
    ("NASCAR Cup", "racing", "nascar-premier"),
    ("PGA", "golf", "pga"),
    ("LPGA", "golf", "lpga"),
    ("LIV Golf", "golf", "liv"),
    ("ATP", "tennis", "atp"),
    ("WTA", "tennis", "wta"),
    ("PLL", "lacrosse", "pll"),
    ("NLL", "lacrosse", "nll"),
    ("FIVB Men", "volleyball", "fivb.m"),
    ("FIVB Women", "volleyball", "fivb.w"),
    ("NRL", "rugby-league", "3"),
    ("AFL", "australian-football", "afl"),
    ("ICC T20", "cricket", "icc.t20"),
    ("IPL", "cricket", "ipl"),
]


def get_json(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def iso(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def norm(value: str) -> str:
    value = str(value or "").lower().replace("&", " and ")
    value = re.sub(r"\b(at|vs\.?|versus)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def title_parts(value: str) -> set[str]:
    return set(norm(value).split())


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


def same_event(candidate: dict, league: str, title: str, start: str) -> bool:
    if candidate.get("league") != league:
        return False
    candidate_start = iso(candidate.get("start"))
    if candidate_start != start:
        return False

    old = title_parts(candidate.get("title") or "")
    new = title_parts(title)
    if old == new:
        return True

    # Team-name feeds frequently differ on suffixes such as FC, University,
    # State, or city abbreviations. Matching the substantial shared tokens is
    # safer than requiring the exact display title.
    shared = old & new
    significant = {token for token in shared if len(token) >= 4}
    return len(significant) >= 2


def main():
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    changed = 0
    added_live = 0
    today = datetime.now(timezone.utc).date()

    for league, sport, slug in ESPN_LEAGUES:
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={today:%Y%m%d}&limit=1000"
        try:
            root = get_json(url)
        except Exception as exc:
            print(f"LIVE RECONCILE: {league}: request failed: {exc}")
            continue
        for remote in root.get("events") or []:
            start = iso(remote.get("date"))
            if not start:
                continue
            title = espn_title(remote, league)
            tag = state_tag(remote)
            matches = [e for e in events if same_event(e, league, title, start)]
            if matches:
                event = matches[0]
                if event.get("tag") != tag:
                    event["tag"] = tag
                    event["sourceDetail"] = "ESPN live-status reconciliation"
                    changed += 1
                continue

            if tag == "LIVE":
                events.append({
                    "league": league,
                    "title": title,
                    "start": start,
                    "tag": "LIVE",
                    "icon": "•",
                    "source": "espn",
                    "sourceDetail": "ESPN live-status reconciliation",
                })
                added_live += 1

    payload["events"] = events
    payload["eventCounts"] = {k: sum(1 for e in events if e.get("league") == k) for k in sorted({e.get("league") for e in events if e.get("league")})}
    if changed or added_live:
        payload.setdefault("repairReport", {})["liveStatusReconciled"] = changed
        payload["repairReport"]["liveEventsAdded"] = added_live
        FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"LIVE RECONCILE: status_updates={changed}; live_events_added={added_live}")


if __name__ == "__main__":
    main()
