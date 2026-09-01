#!/usr/bin/env python3
"""Repair MLB logo gaps using the deterministic canonical MLB catalog."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
PHASE3 = ROOT / "scripts/phase3_visual_enrichment.py"
MLB_ART = "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"

spec = importlib.util.spec_from_file_location("phase3_visual_enrichment", PHASE3)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def clean_name(value: str) -> str:
    """Normalize harmless source decorations before MLB alias resolution."""
    text = str(value or "").upper().strip()
    text = re.sub(r"\b(?:MLB|MAJOR LEAGUE BASEBALL)\b\s*[:\-|]\s*", "", text)
    text = re.sub(r"\s*\((?:MLB|BASEBALL)\)\s*$", "", text)
    return mod.norm(text)


def canonical_team(value: str) -> str:
    normalized = clean_name(value)
    if not normalized:
        return ""

    direct = mod.ALIASES.get(normalized)
    if direct:
        return direct

    # Some providers prepend/append league/source text. Prefer the longest
    # known alias contained as a complete phrase, avoiding substring collisions.
    candidates = []
    for alias, canonical in mod.ALIASES.items():
        alias_norm = mod.norm(alias)
        if not alias_norm:
            continue
        if re.search(rf"(?:^| ){re.escape(alias_norm)}(?: |$)", normalized):
            candidates.append((len(alias_norm), canonical))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return ""


def logo_for(value: str) -> str:
    canonical = canonical_team(value)
    return mod.MLB_CANONICAL_LOGOS.get(canonical, "") if canonical else ""


def is_placeholder(value: str) -> bool:
    text = clean_name(value)
    if not text:
        return True
    return mod.is_mlb_placeholder(text) or bool(re.search(r"\b(?:TBD|WINNER|SEED)\b", text))


def main() -> None:
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    changed = 0
    logo_repairs = 0
    placeholder_repairs = 0
    unresolved = []

    for event in payload.get("events") or []:
        if str(event.get("league") or "").strip() != "MLB":
            continue

        away = str(event.get("away") or "").strip()
        home = str(event.get("home") or "").strip()

        # Unknown postseason participants are not team-logo failures. Keep them
        # on league art, including one-sided TBD/seed/winner matchups.
        if is_placeholder(away) or is_placeholder(home):
            before = (event.get("eventType"), event.get("image"), event.get("awayLogo"), event.get("homeLogo"))
            event["eventType"] = "named_event"
            event["mlbPlaceholder"] = True
            event["leagueArt"] = MLB_ART
            event["image"] = MLB_ART
            event["awayLogo"] = ""
            event["homeLogo"] = ""
            event["artworkReason"] = "MLB placeholder event; team identity not yet determined"
            after = (event.get("eventType"), event.get("image"), event.get("awayLogo"), event.get("homeLogo"))
            if before != after:
                changed += 1
                placeholder_repairs += 1
            continue

        for field, team_field in (("awayLogo", "away"), ("homeLogo", "home")):
            if str(event.get(field) or "").strip():
                continue
            logo = logo_for(str(event.get(team_field) or ""))
            if logo:
                event[field] = logo
                changed += 1
                logo_repairs += 1
            else:
                unresolved.append({
                    "title": str(event.get("title") or ""),
                    "team": str(event.get(team_field) or ""),
                    "field": field,
                })

    report = payload.setdefault("phase3VisualReport", {})
    report["mlbLogoRepair"] = {
        "changed": changed,
        "logoRepairs": logo_repairs,
        "placeholderRepairs": placeholder_repairs,
        "unresolved": unresolved,
    }
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["mlbLogoRepair"], indent=2, ensure_ascii=False))
    if unresolved:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
