#!/usr/bin/env python3
"""Audit unresolved MLB team-logo slots without changing schedule data."""
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
    exact = str(name or "").strip()
    normalized = mod.norm(exact)
    canonical = mod.ALIASES.get(normalized, "")
    return normalized, canonical


def classify_resolution(name: str, cache: dict) -> dict:
    normalized, canonical = alias_info(name)
    cached = exact_cached(cache, name)
    canonical_logo = mod.MLB_CANONICAL_LOGOS.get(canonical, "") if canonical else ""
    # Do not call cached_logo here: this audit deliberately separates the exact
    # persistent-cache match from alias/canonical fallback capability.
    if cached:
        disposition = "persistent_catalog"
    elif canonical:
        # If the exact string is not in the persistent catalog but the alias
        # table maps it to one of the canonical MLB teams, the defect is not
        # inherently an event parser defect. We report the alias/canonical path
        # explicitly so the next fix can be chosen from evidence.
        disposition = "alias_table" if normalized in mod.ALIASES else "normalization"
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

    incomplete = []
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
        away_logo = str(event.get("awayLogo") or "").strip()
        home_logo = str(event.get("homeLogo") or "").strip()
        # The Phase 3 feed is the source of truth for what the UI currently
        # considers unresolved. Do not infer a new logo here.
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
        incomplete.append(row)
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

    def unresolved_variant_rows(counter: Counter, side: str):
        rows = []
        for exact, count in counter.most_common():
            analysis = classify_resolution(exact, cache)
            rows.append({"exact": exact, "count": count, **analysis})
        return rows

    report = {
        "schema_version": 1,
        "league": "MLB",
        "games_total": sum(1 for e in events if str(e.get("league") or "").strip() == "MLB"),
        "incomplete_games": len(incomplete),
        "missing_away_only": len(missing_away),
        "missing_home_only": len(missing_home),
        "both_missing": len(both_missing),
        "missing_slots": len(away_variants) and sum(away_variants.values()) + sum(home_variants.values()),
        "away_variants": unresolved_variant_rows(away_variants, "away"),
        "home_variants": unresolved_variant_rows(home_variants, "home"),
        "missing_away_only_games": missing_away,
        "missing_home_only_games": missing_home,
        "both_missing_games": both_missing,
        "decision_rule": {
            "persistent_catalog": "exact normalized team key already has an MLB logo in team_logo_map.json",
            "alias_table": "exact normalized provider string is explicitly present in the MLB ALIASES table and maps to a canonical team",
            "normalization": "the normalized form is what makes an existing alias/canonical identity match; only choose this after exact-string comparison fails",
            "event_name_parser": "only when the away/home strings themselves are absent or incorrectly extracted from the event title",
        },
        "parser_evidence": {
            "events_with_missing_away_string": sum(1 for r in incomplete if not r["away"]),
            "events_with_missing_home_string": sum(1 for r in incomplete if not r["home"]),
        },
    }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
