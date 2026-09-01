#!/usr/bin/env python3
"""Hydrate the persistent IPL team-logo catalog before visual enrichment.

IPL is cricket, so it is intentionally outside the generic ESPN team catalog.
Prefer ESPN's cricket team endpoint when available, but keep a deterministic
ESPN CDN fallback because the cricket teams endpoint is intermittently absent
from GitHub Actions. The normal refresh remains cache-only and fast.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "team_logo_map.json"
HEADERS = {"User-Agent": "Mozilla/5.0 XSportsX-IPLLogoCatalog/1.1", "Accept": "application/json,text/plain,*/*"}

EXPECTED = {
    "CHENNAI SUPER KINGS": ["CSK", "CHENNAI", "CHENNAI SUPER KINGS"],
    "DELHI CAPITALS": ["DC", "DELHI", "DELHI CAPITALS", "DELHI DAREDEVILS"],
    "GUJARAT TITANS": ["GT", "GUJARAT", "GUJARAT TITANS"],
    "KOLKATA KNIGHT RIDERS": ["KKR", "KOLKATA", "KOLKATA KNIGHT RIDERS"],
    "LUCKNOW SUPER GIANTS": ["LSG", "LUCKNOW", "LUCKNOW SUPER GIANTS"],
    "MUMBAI INDIANS": ["MI", "MUMBAI", "MUMBAI INDIANS"],
    "PUNJAB KINGS": ["PBKS", "PBK", "PUNJAB", "PUNJAB KINGS", "KINGS XI PUNJAB"],
    "RAJASTHAN ROYALS": ["RR", "RAJASTHAN", "RAJASTHAN ROYALS"],
    "ROYAL CHALLENGERS BENGALURU": ["RCB", "ROYAL CHALLENGERS BENGALURU", "ROYAL CHALLENGERS BANGALORE", "BENGALURU"],
    "SUNRISERS HYDERABAD": ["SRH", "SUNRISERS", "SUNRISERS HYDERABAD", "HYDERABAD"],
}

# Verified ESPN cricket team object IDs used by the public ESPN CDN logo path.
# This is deliberately deterministic so a transient ESPN API 404 cannot block
# the entire schedule refresh.
ESPN_TEAM_IDS = {
    "CHENNAI SUPER KINGS": "335974",
    "DELHI CAPITALS": "335975",
    "GUJARAT TITANS": "1298769",
    "KOLKATA KNIGHT RIDERS": "335971",
    "LUCKNOW SUPER GIANTS": "1298768",
    "MUMBAI INDIANS": "335978",
    "PUNJAB KINGS": "335973",
    "RAJASTHAN ROYALS": "335977",
    "ROYAL CHALLENGERS BENGALURU": "335970",
    "SUNRISERS HYDERABAD": "628333",
}


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()


def get_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def team_rows(payload):
    rows = []

    def walk(obj):
        if isinstance(obj, dict):
            team = obj.get("team")
            if isinstance(team, dict):
                rows.append(team)
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(payload)
    out, seen = [], set()
    for team in rows:
        key = str(team.get("id") or team.get("displayName") or team.get("name") or "")
        if key and key not in seen:
            seen.add(key)
            out.append(team)
    return out


def team_name(team):
    for key in ("displayName", "display_name", "shortDisplayName", "name", "abbreviation"):
        value = team.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def team_logo(team):
    for logo in team.get("logos") or []:
        if isinstance(logo, dict) and logo.get("href"):
            return str(logo["href"]).strip()
    return ""


def canonical(name: str) -> str:
    n = norm(name)
    for target, aliases in EXPECTED.items():
        if n == norm(target) or n in {norm(x) for x in aliases}:
            return target
    return ""


def deterministic_logo_url(team: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/cricket/500/{ESPN_TEAM_IDS[team]}.png"


def main():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"version": 4, "teams": {}, "sources": {}}
    teams = cache.setdefault("teams", {})
    sources = cache.setdefault("sources", {})
    found = {}
    errors = []

    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/cricket/ipl/teams?limit=100",
        "https://sports.core.api.espn.com/v2/sports/cricket/leagues/ipl/teams?limit=100",
    ]
    for url in urls:
        try:
            payload = get_json(url)
            for team in team_rows(payload):
                name = team_name(team)
                logo = team_logo(team)
                target = canonical(name)
                if target and logo:
                    found[target] = logo
            if len(found) == len(EXPECTED):
                break
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    # ESPN's cricket API is not reliably exposed from Actions, but its CDN
    # team-logo assets are stable. Fill only unresolved clubs deterministically.
    fallback_count = 0
    for target in EXPECTED:
        if target not in found:
            found[target] = deterministic_logo_url(target)
            fallback_count += 1

    missing = sorted(set(EXPECTED) - set(found))
    if missing:
        raise SystemExit(f"IPL logo hydration incomplete: resolved {len(found)}/{len(EXPECTED)}; missing={missing}; errors={errors}")

    aliases_written = 0
    for target, aliases in EXPECTED.items():
        logo = found[target]
        for alias in aliases + [target]:
            key = f"IPL|{norm(alias)}"
            if teams.get(key) != logo:
                teams[key] = logo
                aliases_written += 1

    source_name = "ESPN cricket IPL teams endpoint + deterministic ESPN CDN fallback"
    sources["IPL"] = {
        "source": source_name,
        "teams": len(found),
        "aliases_written": aliases_written,
        "api_errors": errors,
        "deterministic_fallbacks": fallback_count,
    }
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"IPL logo catalog hydrated: {len(found)}/{len(EXPECTED)} teams; aliases_written={aliases_written}; deterministic_fallbacks={fallback_count}")


if __name__ == "__main__":
    main()
