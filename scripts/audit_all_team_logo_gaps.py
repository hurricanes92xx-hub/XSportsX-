#!/usr/bin/env python3
"""Audit every team-based schedule event for actionable logo gaps.

Does not mutate the schedule feed. Non-team named events and intentional
postseason/placeholder events are excluded from team-logo completeness.
"""
from __future__ import annotations

import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"
OUT = ROOT / "data/all_team_logo_audit.json"
PHASE3 = ROOT / "scripts/phase3_visual_enrichment.py"
CLASSIFIER = ROOT / "scripts/classify_non_team_events.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


phase3 = load_module(PHASE3, "phase3_visual_enrichment")
classifier = load_module(CLASSIFIER, "classify_non_team_events")


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()


def load_json(path: Path, fallback: dict) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else fallback
    except Exception:
        return fallback


def cached(cache: dict, league: str, team: str) -> str:
    teams = cache.get("teams") or {}
    value = teams.get(f"{league}|{norm(team)}")
    return value if isinstance(value, str) else ""


def placeholder(league: str, team: str, event: dict) -> bool:
    n = norm(team)
    if event.get("eventType") == "named_event" or event.get("nonTeamSport") is True:
        return True
    if not n:
        return True
    if n in {"TBD", "TBA", "TO BE DETERMINED", "TO BE ANNOUNCED", "TBD TBD"}:
        return True
    # Generic postseason/seed placeholders across team sports.
    if re.search(r"\b(?:WINNER|LOSER|SEED|WILD CARD|PLAY IN|PLAY-IN|QUARTERFINAL|SEMIFINAL|FINAL)\b", n):
        if not re.search(r"[A-Z]{3,} [A-Z]{3,}", n):
            return True
    if league in {"NCAA FB", "NCAA FCS", "MLB"}:
        if any(x in n for x in ("BOWL", "CHAMPIONSHIP", "PLAYOFF", "CFP", "FCS PLAYOFF")):
            return True
    return False


def resolution(league: str, team: str, cache: dict) -> str:
    if cached(cache, league, team):
        return "persistent_catalog"
    if league == "MLB" and hasattr(phase3, "ALIASES") and phase3.ALIASES.get(norm(team)):
        return "alias_table"
    return "unresolved"


def main() -> None:
    payload = load_json(FEED, {"events": []})
    cache = load_json(CACHE, {"teams": {}})
    events = payload.get("events") or []

    by_league = defaultdict(lambda: {
        "team_games": 0,
        "complete_games": 0,
        "incomplete_games": 0,
        "missing_logo_slots": 0,
        "placeholder_or_named_events": 0,
    })
    missing_variants: dict[str, Counter[str]] = defaultdict(Counter)
    missing_examples: dict[str, list[dict]] = defaultdict(list)
    excluded = Counter()
    total_team_games = total_complete = total_incomplete = total_slots = 0

    for event in events:
        league = str(event.get("league") or "").strip() or "UNKNOWN"
        away = str(event.get("away") or "").strip()
        home = str(event.get("home") or "").strip()

        if event.get("eventType") == "named_event" or event.get("nonTeamSport") is True or classifier.is_non_team_league(league):
            excluded[league] += 1
            by_league[league]["placeholder_or_named_events"] += 1
            continue

        if placeholder(league, away, event) or placeholder(league, home, event):
            excluded[f"{league}:placeholder"] += 1
            by_league[league]["placeholder_or_named_events"] += 1
            continue

        if not away or not home:
            excluded[f"{league}:missing-team-name"] += 1
            continue

        by_league[league]["team_games"] += 1
        total_team_games += 1
        away_logo = str(event.get("awayLogo") or "").strip()
        home_logo = str(event.get("homeLogo") or "").strip()
        missing = []
        if not away_logo:
            missing.append(("away", away))
        if not home_logo:
            missing.append(("home", home))

        if not missing:
            by_league[league]["complete_games"] += 1
            total_complete += 1
            continue

        by_league[league]["incomplete_games"] += 1
        total_incomplete += 1
        by_league[league]["missing_logo_slots"] += len(missing)
        total_slots += len(missing)
        for side, team in missing:
            missing_variants[league][team] += 1
            if len(missing_examples[league]) < 20:
                missing_examples[league].append({
                    "start": event.get("start"),
                    "title": event.get("title"),
                    "side": side,
                    "team": team,
                    "normalized": norm(team),
                    "resolution": resolution(league, team, cache),
                })

    leagues = {}
    for league, stats in sorted(by_league.items(), key=lambda kv: (-kv[1]["incomplete_games"], kv[0])):
        variants = [
            {
                "team": team,
                "count": count,
                "normalized": norm(team),
                "resolution": resolution(league, team, cache),
            }
            for team, count in missing_variants[league].most_common()
        ]
        stats["top_missing_teams"] = variants[:100]
        stats["examples"] = missing_examples[league]
        stats["completion_rate"] = round(
            stats["complete_games"] / stats["team_games"] * 100, 2
        ) if stats["team_games"] else 100.0
        leagues[league] = stats

    report = {
        "schema_version": 1,
        "feed_generated_at": payload.get("generatedAt"),
        "events_total": len(events),
        "team_games": total_team_games,
        "complete_team_games": total_complete,
        "actionable_incomplete_team_games": total_incomplete,
        "missing_logo_slots": total_slots,
        "overall_completion_rate": round(total_complete / total_team_games * 100, 2) if total_team_games else 100.0,
        "excluded_named_or_placeholder_events": sum(excluded.values()),
        "excluded_breakdown": dict(sorted(excluded.items())),
        "priority_leagues": [
            {
                "league": league,
                "incomplete_games": stats["incomplete_games"],
                "missing_logo_slots": stats["missing_logo_slots"],
                "completion_rate": stats["completion_rate"],
            }
            for league, stats in sorted(
                leagues.items(),
                key=lambda kv: (-kv[1]["incomplete_games"], -kv[1]["missing_logo_slots"], kv[0]),
            )
            if stats["incomplete_games"]
        ],
        "leagues": leagues,
        "decision": "Only actionable team-game logo gaps count as defects; named/non-team and intentional placeholder events are excluded.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
