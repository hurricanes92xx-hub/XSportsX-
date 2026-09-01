#!/usr/bin/env python3
"""Audit actionable MLB logo gaps; postseason placeholders use league art."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"
PHASE3 = ROOT / "scripts/phase3_visual_enrichment.py"
OUT = ROOT / "data/mlb_logo_audit.json"

spec = importlib.util.spec_from_file_location("phase3_visual_enrichment", PHASE3)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def exact_cached(cache: dict, name: str) -> str:
    teams = cache.get("teams") or {}
    value = teams.get(f"MLB|{mod.norm(name)}")
    return value if isinstance(value, str) else ""


def alias_info(name: str) -> tuple[str, str]:
    normalized = mod.norm(name)
    return normalized, mod.ALIASES.get(normalized, "")


def classify_resolution(name: str, cache: dict) -> dict:
    normalized, canonical = alias_info(name)
    cached = exact_cached(cache, name)
    canonical_logo = mod.MLB_CANONICAL_LOGOS.get(canonical, "") if canonical else ""
    if cached:
        disposition = "persistent_catalog"
    elif canonical:
        disposition = "alias_table" if normalized in mod.ALIASES else "normalization"
    elif mod.is_mlb_placeholder(name):
        disposition = "league_art_placeholder"
    else:
        disposition = "unresolved"
    return {
        "exact": str(name or ""),
        "normalized": normalized,
        "persistent_exact_match": bool(cached),
        "alias_match": bool(canonical),
        "alias_canonical": canonical,
        "canonical_logo_available": bool(canonical_logo),
        "disposition": disposition,
    }


def main() -> None:
    payload = load_json(FEED)
    cache = load_json(CACHE) if CACHE.exists() else {"teams": {}}
    events = payload.get("events") or []
    actionable = []
    placeholders = []
    missing_away = []
    missing_home = []
    both_missing = []
    away_variants = Counter()
    home_variants = Counter()

    for event in events:
        if str(event.get("league") or "").strip() != "MLB":
            continue
        away = str(event.get("away") or "").strip()
        home = str(event.get("home") or "").strip()
        is_placeholder = bool(event.get("mlbPlaceholder") is True or event.get("eventType") == "named_event" or (away and home and mod.is_mlb_placeholder(away) and mod.is_mlb_placeholder(home)))
        if is_placeholder:
            placeholders.append({
                "title": str(event.get("title") or ""),
                "start": event.get("start"),
                "away": away,
                "home": home,
                "leagueArt": str(event.get("image") or mod.LEAGUE_ART.get("MLB", "")),
            })
            continue
        away_logo = str(event.get("awayLogo") or "").strip()
        home_logo = str(event.get("homeLogo") or "").strip()
        if away_logo and home_logo:
            continue
        row = {
            "title": str(event.get("title") or ""),
            "start": event.get("start"),
            "away": away,
            "home": home,
            "awayLogoPresent": bool(away_logo),
            "homeLogoPresent": bool(home_logo),
            "awayAnalysis": classify_resolution(away, cache),
            "homeAnalysis": classify_resolution(home, cache),
        }
        actionable.append(row)
        if not away_logo:
            away_variants[away] += 1
        if not home_logo:
            home_variants[home] += 1
        if not away_logo and home_logo:
            missing_away.append(row)
        elif away_logo and not home_logo:
            missing_home.append(row)
        else:
            both_missing.append(row)

    def variants(counter):
        return [{"exact": exact, "count": count, **classify_resolution(exact, cache)} for exact, count in counter.most_common()]

    report = {
        "schema_version": 3,
        "league": "MLB",
        "games_total": sum(1 for e in events if str(e.get("league") or "").strip() == "MLB"),
        "placeholder_events": len(placeholders),
        "placeholder_events_use_league_art": True,
        "incomplete_games": len(actionable),
        "actionable_incomplete_games": len(actionable),
        "missing_away_only": len(missing_away),
        "missing_home_only": len(missing_home),
        "both_missing": len(both_missing),
        "missing_logo_slots": sum(away_variants.values()) + sum(home_variants.values()),
        "away_variants": variants(away_variants),
        "home_variants": variants(home_variants),
        "missing_away_only_games": missing_away,
        "missing_home_only_games": missing_home,
        "both_missing_games": both_missing,
        "placeholder_games": placeholders,
        "parser_evidence": {
            "events_with_missing_away_string": sum(1 for r in actionable if not r["away"]),
            "events_with_missing_home_string": sum(1 for r in actionable if not r["home"]),
        },
        "decision": "MLB is complete when actionable_incomplete_games == 0; postseason/seed/TBD placeholders are named events using MLB league card art and are not team-logo failures.",
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if actionable:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
