#!/usr/bin/env python3
"""Repair legacy ESPN logo namespaces and normalize CDN delivery URLs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"

GENERIC = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/500/(\d+)\.png$")
SPORT_NUMERIC = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/(?:football|field-hockey|hockey)/500/(\d+)\.png$")
CFL = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/cfl/500/[^/]+\.png$")
COUNTRY = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/countries/500/[^/]+\.png$")
ESPN_DIRECT = re.compile(r"^https://a\.espncdn\.com/(i/teamlogos/.+)$")
ESPN_COMBINER = re.compile(r"^https://a\.espncdn\.com/combiner/i\?")

# Stable public artwork used only when a retired ESPN namespace cannot be
# translated to a current team-logo URL.
LEAGUE_ART = {
    "CFL": "https://commons.wikimedia.org/wiki/Special:Redirect/file/CFL_Logo.svg",
    "Rugby World Cup": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Rugby_World_Cup_Logo%2C_used_post_RWC_2023.svg",
    "Six Nations": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Guinness_Six_Nations_logo.png",
}


def is_ncaa(league: str) -> bool:
    return league.upper().startswith("NCAA ")


def combiner(path: str) -> str:
    # ESPN's combiner endpoint is the supported image-delivery path. Keep the
    # original asset path intact while asking for a stable 500px rendition.
    return "https://a.espncdn.com/combiner/i?img=" + quote("/" + path.lstrip("/"), safe="/") + "&h=500&w=500"


def repair_url(url: object, league: str) -> tuple[object, bool, str]:
    if not isinstance(url, str):
        return url, False, ""
    value = url.strip()
    if not value.startswith("https://a.espncdn.com/"):
        return value, False, ""

    if is_ncaa(league):
        match = GENERIC.match(value) or SPORT_NUMERIC.match(value)
        if match:
            return combiner(f"i/teamlogos/ncaa/500/{match.group(1)}.png"), True, "ncaa_namespace"

    if league == "CFL" and CFL.match(value):
        return LEAGUE_ART["CFL"], True, "cfl_league_fallback"

    if league in {"Rugby World Cup", "Six Nations"} and COUNTRY.match(value):
        return LEAGUE_ART[league], True, "country_league_fallback"

    direct = ESPN_DIRECT.match(value)
    if direct and not ESPN_COMBINER.match(value):
        return combiner(direct.group(1)), True, "espn_combiner"

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
