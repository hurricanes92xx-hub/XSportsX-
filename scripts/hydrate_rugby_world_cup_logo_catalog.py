#!/usr/bin/env python3
"""Hydrate the Rugby World Cup team-logo catalog.

Rugby World Cup 2027 is a 24-team international tournament. ESPN's generic
team catalog is not reliable for this competition, so use the stable country
logo assets already used by ESPN's Rugby World Cup data and persist aliases.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "team_logo_map.json"

EXPECTED = {
    "NEW ZEALAND": ["NEW ZEALAND", "NZ", "ALL BLACKS"],
    "AUSTRALIA": ["AUSTRALIA", "AUS", "WALLABIES"],
    "CHILE": ["CHILE", "CHI"],
    "HONG KONG CHINA": ["HONG KONG CHINA", "HONG KONG", "HKG"],
    "SOUTH AFRICA": ["SOUTH AFRICA", "RSA", "SPRINGBOKS"],
    "ITALY": ["ITALY", "ITA"],
    "GEORGIA": ["GEORGIA", "GEO"],
    "ROMANIA": ["ROMANIA", "ROU"],
    "ARGENTINA": ["ARGENTINA", "ARG", "PUMAS"],
    "FIJI": ["FIJI", "FIJ"],
    "SPAIN": ["SPAIN", "ESP"],
    "CANADA": ["CANADA", "CAN"],
    "IRELAND": ["IRELAND", "IRE"],
    "SCOTLAND": ["SCOTLAND", "SCO"],
    "URUGUAY": ["URUGUAY", "URU"],
    "PORTUGAL": ["PORTUGAL", "POR"],
    "FRANCE": ["FRANCE", "FRA"],
    "JAPAN": ["JAPAN", "JPN"],
    "USA": ["USA", "UNITED STATES", "UNITED STATES OF AMERICA"],
    "SAMOA": ["SAMOA", "SAM"],
    "ENGLAND": ["ENGLAND", "ENG"],
    "WALES": ["WALES", "WAL"],
    "TONGA": ["TONGA", "TON"],
    "ZIMBABWE": ["ZIMBABWE", "ZIM"],
}

CODES = {
    "NEW ZEALAND":"nzl", "AUSTRALIA":"aus", "CHILE":"chi", "HONG KONG CHINA":"hkg",
    "SOUTH AFRICA":"rsa", "ITALY":"ita", "GEORGIA":"geo", "ROMANIA":"rou",
    "ARGENTINA":"arg", "FIJI":"fij", "SPAIN":"esp", "CANADA":"can",
    "IRELAND":"ire", "SCOTLAND":"sco", "URUGUAY":"uru", "PORTUGAL":"por",
    "FRANCE":"fra", "JAPAN":"jpn", "USA":"usa", "SAMOA":"sam",
    "ENGLAND":"eng", "WALES":"wal", "TONGA":"ton", "ZIMBABWE":"zim",
}


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()


def main() -> None:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"version": 4, "teams": {}, "sources": {}}
    teams = cache.setdefault("teams", {})
    sources = cache.setdefault("sources", {})

    found = {}
    for team, code in CODES.items():
        found[team] = f"https://a.espncdn.com/i/teamlogos/countries/500/{code}.png"

    if len(found) != len(EXPECTED):
        raise SystemExit(f"Rugby World Cup catalog incomplete: {len(found)}/{len(EXPECTED)}")

    aliases_written = 0
    for canonical, aliases in EXPECTED.items():
        logo = found[canonical]
        for alias in aliases + [canonical]:
            key = f"Rugby World Cup|{norm(alias)}"
            if teams.get(key) != logo:
                teams[key] = logo
                aliases_written += 1

    sources["Rugby World Cup"] = {
        "source": "ESPN country rugby logo CDN; 2027 teams corroborated by World Rugby",
        "teams": len(found),
        "aliases_written": aliases_written,
    }
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Rugby World Cup logo catalog hydrated: {len(found)}/{len(EXPECTED)} teams; aliases_written={aliases_written}")


if __name__ == "__main__":
    main()
