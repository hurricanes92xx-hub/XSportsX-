#!/usr/bin/env python3
"""Hydrate the 2026 CFL team-logo catalog from live ESPN scoreboard competitors.

The ESPN CFL Site API /teams catalog currently returns no teams in refresh jobs.
The CFL scoreboard still exposes each competitor's full team object and logo, so
collect the nine current clubs from the 2026 season schedule and persist those
logos for the normal enrichment pass.
"""
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
HEADERS = {"User-Agent": "XSportsX-CFL-LogoCatalog/1.1", "Accept": "application/json"}

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

    # Pull the full 2026 season in month-sized date windows. Scoreboard responses
    # contain competitor.team.logos even though the /teams catalog is empty.
    windows = [
        ("20260501", "20260531"),
        ("20260601", "20260630"),
        ("20260701", "20260731"),
        ("20260801", "20260831"),
        ("20260901", "20260930"),
        ("20261001", "20261031"),
        ("20261101", "20261130"),
    ]
    found = {}
    for start, end in windows:
        url = BASE + "?" + urllib.parse.urlencode({"dates": f"{start}-{end}"})
        root = get_json(url)
        for event in root.get("events") or []:
            for comp in (event.get("competitions") or [{}])[0].get("competitors") or []:
                team = comp.get("team") or {}
                logo = ""
                logos = team.get("logos") or []
                if logos and isinstance(logos[0], dict):
                    logo = str(logos[0].get("href") or "").strip()
                if not logo:
                    continue
                code = str(team.get("abbreviation") or "").strip().upper()
                display = str(team.get("displayName") or team.get("name") or "").strip()
                canonical = code if code in ALIASES else CODE_BY_NORM.get(norm(display))
                if canonical in ALIASES:
                    found[canonical] = (display, logo)

    if len(found) != 9:
        raise RuntimeError(f"ESPN CFL scoreboard resolved only {len(found)}/9 clubs: {sorted(found)}")

    changed = 0
    for code, (display, logo) in found.items():
        for name in set(ALIASES[code]) | {display, code}:
            key = f"CFL|{norm(name)}"
            if cache["teams"].get(key) != logo:
                cache["teams"][key] = logo
                changed += 1

    cache["sources"]["CFL"] = {
        "provider": "ESPN CFL scoreboard competitor catalog",
        "url": BASE,
        "teams": 9,
        "completeCatalog": True,
        "season": 2026,
        "resolvedAt": datetime.now(timezone.utc).isoformat(),
    }
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "teams": 9, "aliases_updated": changed}, sort_keys=True))


if __name__ == "__main__":
    main()

# Refresh trigger: the dedicated CFL workflow runs on this file.
