#!/usr/bin/env python3
"""Fast, provider-first live-state reconciliation across every configured ESPN league.

The canonical schedule is refreshed much less frequently than live state changes, so
this pass deliberately fetches only today's scoreboard for every configured ESPN
league and reconciles state without rebuilding the schedule. Provider state wins;
bounded sport-aware timing inference is used only when a provider omits a usable
state. This keeps LIVE/FINAL transitions accurate without inventing future events.
"""
from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

from refresh_schedules_legacy import ESPN_LEAGUES
from event_identity import event_identity

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
HEADERS = {
    "User-Agent": "XSportsX-LiveSweep/1.0",
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Upper bounds are deliberately conservative: they are only used when the provider
# gives no meaningful in-progress/final state. They prevent stale starts from being
# promoted indefinitely while covering the normal duration of each sport.
MAX_LIVE_HOURS = {
    "baseball": 5.0, "basketball": 3.5, "football": 5.0, "hockey": 4.0,
    "soccer": 3.5, "tennis": 5.0, "volleyball": 4.0, "golf": 10.0,
    "racing": 8.0, "mma": 6.0, "boxing": 6.0, "wrestling": 5.0,
    "lacrosse": 3.5, "rugby": 3.5, "rugby-league": 3.5,
    "cricket": 10.0, "australian-football": 4.0,
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read()


def _fetch_league(meta: tuple[str, str, str, str, int]) -> tuple[str, list[dict], str | None]:
    name, sport, league, icon, _days = meta
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    base = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today}&limit=1000"
    last_error = None
    for url in (base.replace("https://site.api.espn.com", "https://site.web.api.espn.com"), base):
        try:
            root = json.loads(_get(url))
            raw = root.get("events")
            return name, raw if isinstance(raw, list) else [], None
        except Exception as exc:
            last_error = str(exc)
    return name, [], last_error


def _state(status: dict) -> str:
    typ = status.get("type") or {}
    values = [
        typ.get("state"), typ.get("name"), typ.get("detail"),
        typ.get("shortDetail"), status.get("displayClock"), status.get("period"),
    ]
    text = " ".join(str(v or "") for v in values).strip().lower()
    state = str(typ.get("state") or "").lower()
    if state == "post" or re.search(r"\b(final|final/ot|final/so|complete|completed|postponed|cancelled|canceled)\b", text):
        return "FINAL"
    if state == "in" or re.search(r"\b(in progress|live|halftime|half time|q[1-4]|[1-9][0-9]?th|period [1-9]|set [1-9]|inning|innings)\b", text):
        return "LIVE"
    return "UPCOMING"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _espn_event(name: str, icon: str, event: dict) -> dict | None:
    start = event.get("date")
    if not start:
        return None
    comp = (event.get("competitions") or [{}])[0]
    teams = comp.get("competitors") or []
    home_obj = next((x for x in teams if x.get("homeAway") == "home"), {})
    away_obj = next((x for x in teams if x.get("homeAway") == "away"), {})
    home = (home_obj.get("team") or {}).get("shortDisplayName") or (home_obj.get("team") or {}).get("displayName") or ""
    away = (away_obj.get("team") or {}).get("shortDisplayName") or (away_obj.get("team") or {}).get("displayName") or ""
    e = {
        "league": name,
        "title": f"{away} @ {home}" if home and away else event.get("name") or event.get("shortName") or name,
        "start": start,
        "startUtc": start,
        "tag": _state(comp.get("status") or {}),
        "icon": icon,
        "source": "espn-live-sweep",
        "providerEventId": f"espn:{event.get('id')}" if event.get("id") else "",
    }
    if home: e["home"] = home
    if away: e["away"] = away
    for side, key in (("home", "homeTeamId"), ("away", "awayTeamId")):
        team = ((home_obj if side == "home" else away_obj).get("team") or {})
        if team.get("id"): e[key] = str(team["id"])
    status = comp.get("status") or {}
    typ = status.get("type") or {}
    for key in ("shortDetail", "detail", "displayClock", "period"):
        if status.get(key) is not None: e[f"provider_{key}"] = status[key]
        elif typ.get(key) is not None: e[f"provider_{key}"] = typ[key]
    return e


def _key(event: dict) -> tuple[str, str, str]:
    return (
        str(event.get("league") or "").strip().lower(),
        str(event.get("providerEventId") or "").strip().lower(),
        str(event.get("startUtc") or event.get("start") or ""),
    )


def _merge_key(event: dict) -> tuple[str, str]:
    league = str(event.get("league") or "").strip().lower()
    title = str(event.get("title") or "").strip().lower()
    # Team/title aliases are handled by canonical identity later. For this pass,
    # provider IDs are the strongest exact join and title+league is the safe fallback.
    return league, re.sub(r"[^a-z0-9]+", " ", title).strip()


def _within_window(event: dict, now: datetime) -> bool:
    start = _parse_dt(event.get("startUtc") or event.get("start"))
    if not start or start > now:
        return False
    sport = str(event.get("sport") or "").lower()
    league = str(event.get("league") or "").lower()
    hours = MAX_LIVE_HOURS.get(sport)
    if hours is None:
        for key, value in MAX_LIVE_HOURS.items():
            if key in league:
                hours = value
                break
    return bool(hours and now - start <= timedelta(hours=hours))


def main() -> None:
    if not FEED.exists():
        raise SystemExit("ERROR: schedule_feed.json does not exist")
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    now = datetime.now(timezone.utc)

    results: list[tuple[str, list[dict], str | None]] = []
    with ThreadPoolExecutor(max_workers=min(12, len(ESPN_LEAGUES) or 1)) as pool:
        futures = [pool.submit(_fetch_league, meta) for meta in ESPN_LEAGUES]
        for future in as_completed(futures):
            results.append(future.result())

    by_provider = {}
    live_provider = 0
    final_provider = 0
    failed = []
    fetched_events = 0
    for name, raw, error in results:
        if error:
            failed.append(name)
            continue
        meta = next((m for m in ESPN_LEAGUES if m[0] == name), None)
        if not meta:
            continue
        _, _, _, icon, _ = meta
        for raw_event in raw:
            e = _espn_event(name, icon, raw_event)
            if not e:
                continue
            fetched_events += 1
            by_provider[e.get("providerEventId", "")] = e
            if e["tag"] == "LIVE": live_provider += 1
            elif e["tag"] == "FINAL": final_provider += 1

    # Exact provider IDs first, then a conservative league/title/start join.
    changed = 0
    live_ids = set()
    final_ids = set()
    for event in events:
        pid = str(event.get("providerEventId") or "")
        fresh = by_provider.get(pid) if pid else None
        if fresh is None:
            # Match same league/title and within 20 minutes. This is deliberately
            # narrower than canonical identity so similarly named events cannot collide.
            league, title = _merge_key(event)
            start = _parse_dt(event.get("startUtc") or event.get("start"))
            if start:
                for candidate in by_provider.values():
                    if _merge_key(candidate) == (league, title):
                        cstart = _parse_dt(candidate.get("startUtc"))
                        if cstart and abs(cstart - start) <= timedelta(minutes=20):
                            fresh = candidate
                            break
        if fresh:
            old_tag = event.get("tag")
            event.update({k: v for k, v in fresh.items() if v not in (None, "")})
            if old_tag != event.get("tag"): changed += 1
            if event.get("tag") == "LIVE": live_ids.add(str(event.get("id") or event_identity(event.get("league"), event.get("title"), event.get("startUtc"), event.get("home"), event.get("away"))))
            if event.get("tag") == "FINAL": final_ids.add(str(event.get("id") or event_identity(event.get("league"), event.get("title"), event.get("startUtc"), event.get("home"), event.get("away"))))

    # Add provider events missing from the canonical feed. These are the important
    # "we missed the game entirely" repairs, not just state flips.
    existing_provider = {str(e.get("providerEventId") or "") for e in events if e.get("providerEventId")}
    added = 0
    for pid, fresh in by_provider.items():
        if not pid or pid in existing_provider:
            continue
        if fresh.get("tag") not in {"LIVE", "UPCOMING"}:
            continue
        fresh["sport"] = str(next((m[1] for m in ESPN_LEAGUES if m[0] == fresh.get("league")), "other")).lower()
        fresh["id"] = event_identity(fresh.get("league"), fresh.get("title"), fresh.get("startUtc"), fresh.get("home"), fresh.get("away"))
        events.append(fresh)
        added += 1

    # Bounded inference repairs stale/missing provider states from non-ESPN sources.
    # Never infer FINAL; finalization remains provider/official evidence only.
    inferred = 0
    for event in events:
        if event.get("tag") == "FINAL":
            continue
        if _within_window(event, now):
            start = _parse_dt(event.get("startUtc") or event.get("start"))
            if start and start <= now and event.get("tag") != "LIVE":
                event["tag"] = "LIVE"
                event["liveStateSource"] = "bounded-timing-inference"
                inferred += 1

    events.sort(key=lambda e: str(e.get("startUtc") or e.get("start") or ""))
    payload["events"] = events
    payload["liveSweep"] = {
        "schema": 1,
        "checkedAtUtc": now.isoformat().replace("+00:00", "Z"),
        "leaguesChecked": len(ESPN_LEAGUES),
        "providerEventsFetched": fetched_events,
        "providerLive": live_provider,
        "providerFinal": final_provider,
        "stateChanges": changed,
        "eventsAdded": added,
        "boundedTimingPromotions": inferred,
        "failedLeagues": sorted(failed),
        "liveCountAfterSweep": sum(1 for e in events if e.get("tag") == "LIVE"),
    }
    payload["eventCounts"] = {}
    for event in events:
        league = event.get("league", "Unknown")
        payload["eventCounts"][league] = payload["eventCounts"].get(league, 0) + 1
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["liveSweep"], indent=2))


if __name__ == "__main__":
    main()
