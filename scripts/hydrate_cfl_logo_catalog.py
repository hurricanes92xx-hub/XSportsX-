#!/usr/bin/env python3
"""Hydrate the 2026 CFL team-logo catalog from ESPN Core API.

The ESPN Site API CFL /teams endpoint currently returns an empty catalog in
refresh jobs. ESPN's documented Core API still exposes the CFL team collection,
so use that endpoint as the authoritative fallback and resolve each team ref to
its full team object/logo. The catalog is only nine current CFL clubs.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "team_logo_map.json"
HEADERS = {"User-Agent": "XSportsX-CFL-LogoCatalog/1.0", "Accept": "application/json"}
BASE = "https://sports.core.api.espn.com/v2/sports/football/leagues/cfl"

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


def norm(value: str) -> str:
    value = str(value or "").upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def get_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def resolve_ref(ref: str):
    return get_json(ref.replace("http://", "https://"))


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"version": 4, "teams": {}, "sources": {}}
    cache.setdefault("teams", {})
    cache.setdefault("sources", {})

    root = get_json(f"{BASE}/teams?limit=100")
    items = root.get("items") or []
    if not items:
        raise RuntimeError("ESPN Core CFL team collection returned no items")

    resolved = []
    for item in items:
        ref = item.get("$ref") if isinstance(item, dict) else None
        if not ref:
            continue
        team = resolve_ref(ref)
        logos = team.get("logos") or []
        logo = ""
        if logos and isinstance(logos[0], dict):
            logo = str(logos[0].get("href") or "").strip()
        if not logo:
            continue
        code = str(team.get("abbreviation") or "").strip().upper()
        display = str(team.get("displayName") or team.get("name") or "").strip()
        if code in ALIASES:
            resolved.append((code, display, logo))

    if len({code for code, _, _ in resolved}) != 9:
        raise RuntimeError(f"ESPN Core CFL catalog resolved only {len({code for code, _, _ in resolved})}/9 clubs")

    changed = 0
    for code, display, logo in resolved:
        names = set(ALIASES[code]) | {display, code}
        for name in names:
            key = f"CFL|{norm(name)}"
            if cache["teams"].get(key) != logo:
                cache["teams"][key] = logo
                changed += 1

    cache["sources"]["CFL"] = {
        "provider": "ESPN Core API team catalog",
        "url": f"{BASE}/teams?limit=100",
        "teams": 9,
        "completeCatalog": True,
        "resolvedAt": datetime.now(timezone.utc).isoformat(),
    }
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "teams": 9, "aliases_updated": changed}, sort_keys=True))


if __name__ == "__main__":
    main()
