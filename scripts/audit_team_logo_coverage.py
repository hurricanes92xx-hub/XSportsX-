#!/usr/bin/env python3
"""Audit actual team-game logo coverage.

Non-team sports (fights, racing, individual competitions) are named events and
must not be counted as two-team logo failures. This audit therefore uses the
final eventType classification produced by classify_non_team_events.py and
reports only real team games with missing away/home artwork.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
OUT = ROOT / "data" / "team_logo_coverage_audit.json"
HYDRATOR = ROOT / "scripts" / "hydrate_remaining_team_logo_catalogs.py"


def is_placeholder(value: object) -> bool:
    text = str(value or "").strip().upper()
    return text in {"", "TBD", "TBA", "TBC", "UNKNOWN", "TBD TEAM", "TBA TEAM"}


def main() -> None:
    # Make the remaining-team resolver part of the canonical audit boundary so
    # the final refresh cannot publish a feed before AFL/NBA/NRL/PLL/UEL logos
    # have been applied. The resolver is idempotent and also updates the cache.
    subprocess.run([sys.executable, str(HYDRATOR)], cwd=ROOT, check=True)

    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    by_league: dict[str, dict] = defaultdict(lambda: {
        "team_games": 0,
        "complete": 0,
        "missing_logo_slots": 0,
        "missing_away": 0,
        "missing_home": 0,
        "placeholder_games": 0,
        "examples": [],
    })
    non_team = 0
    named_events = 0
    total_team_games = total_complete = total_missing_slots = 0

    for event in events:
        event_type = str(event.get("eventType") or "").strip()
        if event_type != "team_game":
            if event.get("nonTeamSport") is True or event_type == "named_event":
                non_team += 1
            named_events += 1
            continue

        league = str(event.get("league") or "").strip() or "UNKNOWN"
        row = by_league[league]
        row["team_games"] += 1
        total_team_games += 1

        away = str(event.get("away") or "").strip()
        home = str(event.get("home") or "").strip()
        away_logo = str(event.get("awayLogo") or "").strip()
        home_logo = str(event.get("homeLogo") or "").strip()

        if is_placeholder(away) or is_placeholder(home):
            row["placeholder_games"] += 1
            continue

        missing_away = not away_logo
        missing_home = not home_logo
        if missing_away or missing_home:
            row["missing_logo_slots"] += int(missing_away) + int(missing_home)
            row["missing_away"] += int(missing_away)
            row["missing_home"] += int(missing_home)
            total_missing_slots += int(missing_away) + int(missing_home)
            if len(row["examples"]) < 25:
                row["examples"].append({
                    "title": event.get("title"),
                    "start": event.get("start"),
                    "away": away,
                    "home": home,
                    "missing_away": missing_away,
                    "missing_home": missing_home,
                })
        else:
            row["complete"] += 1
            total_complete += 1

    leagues = {k: by_league[k] for k in sorted(by_league)}
    actionable = {
        k: v for k, v in leagues.items() if v["missing_logo_slots"] or v["team_games"]
    }
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "events_total": len(events),
        "team_games": total_team_games,
        "team_games_complete": total_complete,
        "team_games_with_missing_logos": sum(1 for v in leagues.values() if v["missing_logo_slots"]),
        "missing_logo_slots": total_missing_slots,
        "named_or_non_team_events": named_events,
        "non_team_events_identified": non_team,
        "actionable_leagues": actionable,
        "all_leagues": leagues,
        "rule": "Only eventType=team_game counts toward team-logo coverage. named_event/nonTeamSport events are excluded from team-logo failures.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "team_games": total_team_games,
        "complete": total_complete,
        "missing_logo_slots": total_missing_slots,
        "leagues_with_actionable_gaps": sorted(actionable),
        "non_team_events_excluded": non_team,
    }, indent=2))
    for league, row in actionable.items():
        if row["missing_logo_slots"]:
            print(f"{league}: games={row['team_games']} complete={row['complete']} missing_slots={row['missing_logo_slots']} missing_away={row['missing_away']} missing_home={row['missing_home']}")


if __name__ == "__main__":
    main()
