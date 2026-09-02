#!/usr/bin/env python3
"""Repair legacy ESPN logo namespaces and durable league-art fallbacks."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"

GENERIC = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/500/(\d+)\.png$")
SPORT_NUMERIC = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/(?:football|field-hockey|hockey)/500/(\d+)\.png$")
CFL = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/cfl/500/[^/]+\.png$")
COUNTRY = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/countries/500/[^/]+\.png$")
LONDON_LIONS_OLD = re.compile(r"^https://commons\.wikimedia\.org/wiki/Special:Redirect/file/London%20Lions%20logo%20\(2025\)\.png$")

LEAGUE_ART = {
    "CFL": "https://commons.wikimedia.org/wiki/Special:Redirect/file/CFL_Logo.svg",
    "Rugby World Cup": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Rugby_World_Cup_Logo%2C_used_post_RWC_2023.svg",
    "Six Nations": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Guinness_Six_Nations_logo.png",
}

# Official London Lions 2025+ brand asset. The old Wikimedia redirect was a
# dead 404 and was incorrectly attached to the AFL feed's London Lions row.
LONDON_LIONS_OFFICIAL = "https://cdn.prod.website-files.com/6137737fec180a1d19af6471/68779ef01c49026774e65581_Artboard%202%20copy%202.png"


def is_ncaa(league: str) -> bool:
    return league.upper().startswith("NCAA ")


def repair_url(url: object, league: str) -> tuple[object, bool, str]:
    if not isinstance(url, str):
        return url, False, ""
    value = url.strip()

    if LONDON_LIONS_OLD.match(value):
        return LONDON_LIONS_OFFICIAL, True, "london_lions_official"

    if not value.startswith("https://a.espncdn.com/"):
        return value, False, ""

    if is_ncaa(league):
        match = GENERIC.match(value) or SPORT_NUMERIC.match(value)
        if match:
            return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{match.group(1)}.png", True, "ncaa_namespace"

    if league == "CFL" and CFL.match(value):
        return LEAGUE_ART["CFL"], True, "cfl_league_fallback"

    if league in {"Rugby World Cup", "Six Nations"} and COUNTRY.match(value):
        return LEAGUE_ART[league], True, "country_league_fallback"

    return value, False, ""


def main() -> None:
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    changed_feed = 0
    reasons: dict[str, int] = {}
    for event in feed.get("events") or []:
        league = str(event.get("league") or "").strip()
        for field in ("awayLogo", "homeLogo", "logo", "leagueLogo"):
            repaired, changed, reason = repair_url(event.get(field), league)
            if changed:
                event[field] = repaired
                changed_feed += 1
                reasons[reason] = reasons.get(reason, 0) + 1

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    teams = cache.get("teams") or {}
    changed_cache = 0
    for key, value in list(teams.items()):
        text = str(key)
        league = text.split("|", 1)[0].strip() if "|" in text else ""
        repaired, changed, reason = repair_url(value, league)
        if changed:
            teams[key] = repaired
            changed_cache += 1
            reasons[f"cache_{reason}"] = reasons.get(f"cache_{reason}", 0) + 1
    cache["teams"] = teams

    FEED.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"feed_urls_repaired": changed_feed, "cache_urls_repaired": changed_cache, "reasons": reasons}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
