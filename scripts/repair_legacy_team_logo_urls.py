#!/usr/bin/env python3
"""Repair legacy ESPN team-logo URL namespaces in the active feed and cache.

Older catalog hydrators stored ESPN's generic numeric `/500/<id>.png` paths.
For NCAA teams the live CDN namespace is `/ncaa/500/<id>.png`. The same applies
to the old field-hockey and hockey numeric paths used by NCAA catalogs.
This pass rewrites only deterministic namespace drift; it does not invent team
identities or weaken HTTP validation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
CACHE = ROOT / "data/team_logo_map.json"

GENERIC = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/500/(\d+)\.png$")
FIELD_HOCKEY = re.compile(r"^https://a\.espncdn\.com/i/teamlogos/(?:field-hockey|hockey)/500/(\d+)\.png$")

NCAA_LEAGUES = {
    "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB", "NCAA Baseball",
    "NCAA Softball", "NCAA Men's Hockey", "NCAA Women's Hockey",
    "NCAA Men's Soccer", "NCAA Women's Soccer", "NCAA Men's Lacrosse",
    "NCAA Women's Lacrosse", "NCAA Men's Volleyball", "NCAA Women's Volleyball",
    "NCAA Men's Water Polo", "NCAA Women's Water Polo", "NCAA Women's Field Hockey",
    "NCAA Beach Volleyball", "NCAA Gymnastics", "NCAA Swimming & Diving",
    "NCAA Track & Field", "NCAA Wrestling",
}


def repair_url(url: object, league: str) -> tuple[object, bool]:
    if not isinstance(url, str) or not url.startswith("https://a.espncdn.com/"):
        return url, False
    if league not in NCAA_LEAGUES:
        return url, False
    match = GENERIC.match(url) or FIELD_HOCKEY.match(url)
    if not match:
        return url, False
    return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{match.group(1)}.png", True


def main() -> None:
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    changed_feed = 0
    for event in feed.get("events") or []:
        league = str(event.get("league") or "").strip()
        for field in ("awayLogo", "homeLogo", "logo", "leagueLogo"):
            value = event.get(field)
            repaired, changed = repair_url(value, league)
            if changed:
                event[field] = repaired
                changed_feed += 1

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    changed_cache = 0
    teams = cache.get("teams") or {}
    for key, value in list(teams.items()):
        league = str(key).split("|", 1)[0] if "|" in str(key) else ""
        repaired, changed = repair_url(value, league)
        if changed:
            teams[key] = repaired
            changed_cache += 1
    cache["teams"] = teams

    FEED.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"feed_urls_repaired": changed_feed, "cache_urls_repaired": changed_cache}, indent=2))


if __name__ == "__main__":
    main()
