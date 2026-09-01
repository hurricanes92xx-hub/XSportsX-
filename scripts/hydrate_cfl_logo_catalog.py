#!/usr/bin/env python3
"""Hydrate the 2026 CFL team-logo catalog from ESPN scoreboard data with a deterministic CDN fallback."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "team_logo_map.json"
BASE = "https://site.api.espn.com/apis/site/v2/sports/football/cfl/scoreboard"
HEADERS = {"User-Agent": "XSportsX-CFL-LogoCatalog/1.2", "Accept": "application/json"}

ALIASES = {
    "BC": ["BC LIONS", "BRITISH COLUMBIA", "LIONS"],
    "CGY": ["CALGARY STAMPEDERS", "CALGARY", "STAMPEDERS"],
    "EDM": ["EDMONTON ELKS", "EDMONTON", "ELKS"],
    "HAM": ["HAMILTON TIGER CATS", "HAMILTON TIGER-CATS", "HAMILTON", "TIGER CATS", "TIGER-CATS"],
    "MTL": ["MONTREAL ALOUETTES", "MONTREAL", "ALOUETTES", "MONTRÉAL"],
    "OTT": ["OTTAWA REDBLACKS", "OTTAWA", "REDBLACKS", "RED BLACKS"],
    "SSK": ["SASKATCHEWAN ROUGHRIDERS", "SASKATCHEWAN", "ROUGHRIDERS", "ROUGH RIDERS"],
    "TOR": ["TORONTO ARGONAUTS", "TORONTO", "ARGONAUTS"],
    "WPG": ["WINNIPEG BLUE BOMBERS", "WINNIPEG", "BLUE BOMBERS"],
}
CODE_BY_NORM = {re.sub(r"[^A-Z0-9]+", " ", name.upper()).strip(): code for code, names in ALIASES.items() for name in [code, *names]}

# Deterministic ESPN CDN paths. This is the last-resort path when ESPN's CFL
# scoreboard/team endpoints are unavailable during a GitHub Actions refresh.
STATIC_LOGOS = {
    code: f"https://a.espncdn.com/i/teamlogos/cfl/500/{code.lower()}.png"
    for code in ALIASES
}


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()


def get_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"version": 4, "teams": {}, "sources": {}}
    cache.setdefault("teams", {})
    cache.setdefault("sources", {})

    windows = [
        ("20260501", "20260531"), ("20260601", "20260630"),
        ("20260701", "20260731"), ("20260801", "20260831"),
        ("20260901", "20260930"), ("20261001", "20261031"),
        ("20261101", "20261130"),
    ]
    found = {}
    for start, end in windows:
        try:
            url = BASE + "?" + urllib.parse.urlencode({"dates": f"{start}-{end}"})
            root = get_json(url)
        except Exception as exc:
            print(f"ESPN CFL scoreboard window failed {start}-{end}: {exc}")
            continue
        for event in root.get("events") or []:
            for comp in (event.get("competitions") or [{}])[0].get("competitors") or []:
                team = comp.get("team") or {}
                logos = team.get("logos") or []
                logo = str(logos[0].get("href") or "").strip() if logos and isinstance(logos[0], dict) else ""
                if not logo:
                    continue
                code = str(team.get("abbreviation") or "").strip().upper()
                display = str(team.get("displayName") or team.get("name") or "").strip()
                canonical = code if code in ALIASES else CODE_BY_NORM.get(norm(display))
                if canonical in ALIASES:
                    found[canonical] = (display, logo)

    # ESPN's CFL scoreboard has intermittently returned an empty event set from
    # CI. Use the stable CDN naming convention so the refresh remains deterministic.
    source_provider = "ESPN CFL scoreboard competitor catalog"
    if len(found) != 9:
        print(f"Scoreboard resolved {len(found)}/9 CFL clubs; filling missing clubs from ESPN CDN fallback")
        for code in ALIASES:
            found.setdefault(code, (code, STATIC_LOGOS[code]))
        source_provider = "ESPN CFL scoreboard + deterministic ESPN CDN fallback"

    if len(found) != 9:
        raise RuntimeError(f"CFL logo catalog resolved only {len(found)}/9 clubs: {sorted(found)}")

    changed = 0
    for code, (display, logo) in found.items():
        for name in set(ALIASES[code]) | {display, code}:
            key = f"CFL|{norm(name)}"
            if cache["teams"].get(key) != logo:
                cache["teams"][key] = logo
                changed += 1

    cache["sources"]["CFL"] = {
        "provider": source_provider,
        "url": BASE,
        "teams": 9,
        "completeCatalog": True,
        "season": 2026,
        "resolvedAt": datetime.now(timezone.utc).isoformat(),
    }
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "teams": 9, "aliases_updated": changed, "provider": source_provider}, sort_keys=True))


if __name__ == "__main__":
    main()

# Refresh trigger: the dedicated CFL workflow runs on this file.
