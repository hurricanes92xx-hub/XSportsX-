#!/usr/bin/env python3
"""Resolve NCAA FB/FCS schedule-name variants against the persistent logo catalog.

This stays entirely inside the cached catalog: no logo discovery/network calls.
The schedule feeds use a mix of ESPN display names, short names, abbreviations and
mascot-qualified names; the catalog contains several canonical variants for the
same team. We add deterministic aliases and a conservative unique-core fallback.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
CACHE = ROOT / "data" / "team_logo_map.json"

LEAGUES = {"NCAA FB", "NCAA FCS"}

# Schedule/display variants observed in the audit. Values are canonical catalog
# names (the cache already contains the logo for one or more of these forms).
ALIASES = {
    "MIAMI OH REDHAWKS": ["MIAMI REDHAWKS", "MIAMI OH"],
    "TEXAS A M AGGIES": ["TEXAS A M", "TEXAS A&M", "TEXAS AM"],
    "TEXAS A M": ["TEXAS A M", "TEXAS A&M", "TEXAS AM"],
    "LOUISIANA RAGIN CAJUNS": ["LOUISIANA", "LOUISIANA RAGIN CAJUNS"],
    "GARDNER WEBB": ["GARDNER WEBB", "GARDNER WEBB RUNNIN BULLDOGS"],
    "GARDNER WEBB RUNNIN BULLDOGS": ["GARDNER WEBB", "GARDNER WEBB RUNNIN BULLDOGS"],
    "AR PINE BLUFF": ["ARKANSAS PINE BLUFF", "AR PINE BLUFF", "ARKANSAS PINE BLUFF GOLDEN LIONS"],
    "ARKANSAS PINE BLUFF GOLDEN LIONS": ["ARKANSAS PINE BLUFF", "AR PINE BLUFF"],
    "NC A T": ["NORTH CAROLINA A T", "NORTH CAROLINA A T AGGIES", "NC A T"],
    "NORTH CAROLINA A T AGGIES": ["NORTH CAROLINA A T", "NC A T"],
    "UT RIO GRANDE": ["UT RIO GRANDE VALLEY", "UT RIO GRANDE VALLEY VAQUEROS"],
    "UT RIO GRANDE VALLEY VAQUEROS": ["UT RIO GRANDE VALLEY", "UT RIO GRANDE"],
    "N WESTERN ST": ["NORTHWESTERN STATE", "NORTHWESTERN STATE DEMONS"],
    "EAST TEXAS A M": ["EAST TEXAS A M", "EAST TEXAS A M LIONS"],
    "EAST TEXAS A M LIONS": ["EAST TEXAS A M", "EAST TEXAS A M LIONS"],
    "WILLIAM MARY": ["WILLIAM MARY", "WILLIAM MARY TRIBE"],
    "WILLIAM MARY TRIBE": ["WILLIAM MARY", "WILLIAM MARY TRIBE"],
    "BETHUNE COOKMAN WILDCATS": ["BETHUNE COOKMAN", "BETHUNE COOKMAN WILDCATS"],
    "PRAIRIE VIEW A M PANTHERS": ["PRAIRIE VIEW A M", "PRAIRIE VIEW A M PANTHERS"],
    "ALABAMA A M BULLDOGS": ["ALABAMA A M", "ALABAMA A M BULLDOGS"],
    "ST THOMAS TOMMIES": ["ST THOMAS", "ST THOMAS TOMMIES"],
    "STEPHEN F AUSTIN LUMBERJACKS": ["STEPHEN F AUSTIN", "STEPHEN F AUSTIN LUMBERJACKS"],
    "CHICAGO STATE COUGARS": ["CHICAGO STATE", "CHICAGO STATE COUGARS"],
    "VIRGINIA LYNCHBURG DRAGONS": ["VIRGINIA LYNCHBURG", "VIRGINIA LYNCHBURG DRAGONS"],
    "KENTUCKY CHRISTIAN KNIGHTS": ["KENTUCKY CHRISTIAN", "KENTUCKY CHRISTIAN KNIGHTS"],
    "CENTRAL STATE OH MARAUDERS": ["CENTRAL STATE OH", "CENTRAL STATE OH MARAUDERS"],
    "ARKANSAS BAPTIST BUFFALOES": ["ARKANSAS BAPTIST", "ARKANSAS BAPTIST BUFFALOES"],
    "WEBBER INTERNATIONAL WARRIORS": ["WEBBER INTERNATIONAL", "WEBBER INTERNATIONAL WARRIORS"],
    "LANE DRAGONS": ["LANE", "LANE DRAGONS"],
    "MILES COLLEGE GOLDEN BEARS": ["MILES COLLEGE", "MILES COLLEGE GOLDEN BEARS"],
    "TEXAS WESLEYAN RAMS": ["TEXAS WESLEYAN", "TEXAS WESLEYAN RAMS"],
    "THOMAS MORE COLLEGE SAINTS": ["THOMAS MORE", "THOMAS MORE COLLEGE", "THOMAS MORE COLLEGE SAINTS"],
    "DICKINSON PA RED DEVILS": ["DICKINSON PA", "DICKINSON PA RED DEVILS"],
    "LINCOLN PA LIONS": ["LINCOLN PA", "LINCOLN PA LIONS"],
    "POINT UNIVERSITY SKYHAWKS": ["POINT UNIVERSITY", "POINT UNIVERSITY SKYHAWKS"],
    "RIO GRANDE RED STORM": ["RIO GRANDE", "RIO GRANDE RED STORM"],
    "MOREHOUSE COLLEGE MAROON TIGERS": ["MOREHOUSE COLLEGE", "MOREHOUSE COLLEGE MAROON TIGERS"],
    "UFTL EAGLES": ["UFTL", "UFTL EAGLES"],
}

# Mascot words are deliberately limited. The fallback only applies when the
# remaining core identifies exactly one cached name, preventing accidental
# cross-team matches such as two schools sharing a mascot.
MASCOTS = {
    "BULLDOGS", "BULLDOG", "WILDCATS", "EAGLES", "LIONS", "TIGERS", "PANTHERS",
    "HAWKS", "TOMMIES", "TRIBE", "REDHAWKS", "REDBIRDS", "BEARS", "KNIGHTS",
    "DRAGONS", "WARRIORS", "RAMS", "SAINTS", "RED DEVILS", "GOLDEN BEARS",
    "MAROON TIGERS", "SKYHAWKS", "BUFFALOES", "RUNNIN BULLDOGS", "LUMBERJACKS",
    "VAQUEROS", "GOLDEN LIONS", "DEMONS", "COUGARS", "MARAUDERS", "EAGLES",
}

def norm(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())).strip()

def placeholder(value: str) -> bool:
    n = norm(value)
    return not n or n in {"TBD", "TBA", "UNKNOWN", "WINNER", "LOSER", "HIGHER SEED", "LOWER SEED"} or bool(re.search(r"\b(?:SEED|WINNER|LOSER|CHAMPION|RUNNER UP)\b", n))

def load_json(path: Path, default):
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else default
    except Exception:
        return default

def strip_mascot(name: str) -> str:
    tokens = norm(name).split()
    while tokens and tokens[-1] in {"BULLDOGS","BULLDOG","WILDCATS","EAGLES","LIONS","TIGERS","PANTHERS","HAWKS","TOMMIES","TRIBE","REDHAWKS","BEARS","KNIGHTS","DRAGONS","WARRIORS","RAMS","SAINTS","BUFFALOES","DEMONS","COUGARS","MARAUDERS","VAQUEROS","LUMBERJACKS","SKYHAWKS"}:
        tokens.pop()
    return " ".join(tokens)

def resolve(cache: dict, league: str, team: str) -> str:
    teams = cache.get("teams") or {}
    n = norm(team)
    direct = teams.get(f"{league}|{n}")
    if isinstance(direct, str) and direct:
        return direct
    for candidate in ALIASES.get(n, []):
        v = teams.get(f"{league}|{norm(candidate)}")
        if isinstance(v, str) and v:
            return v
    # Conservative fallback: compare mascot-stripped cores. Only accept a
    # single logo URL, and never guess across multiple different logos.
    core = strip_mascot(n)
    if not core:
        return ""
    matches = set()
    prefix = f"{league}|"
    for key, logo in teams.items():
        if not key.startswith(prefix) or not isinstance(logo, str) or not logo:
            continue
        candidate = key[len(prefix):]
        ccore = strip_mascot(candidate)
        if ccore == core or ccore.startswith(core + " ") or core.startswith(ccore + " "):
            matches.add(logo)
    return next(iter(matches)) if len(matches) == 1 else ""

def split_title(title: str):
    for pattern in (r"^(.+?)\s+@\s+(.+)$", r"^(.+?)\s+AT\s+(.+)$", r"^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$"):
        m = re.match(pattern, str(title or "").strip(), re.I)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", ""

def main():
    feed = load_json(FEED, {})
    cache = load_json(CACHE, {"teams": {}})
    events = feed.get("events") or []
    changed = 0
    unresolved = []
    for e in events:
        league = str(e.get("league") or "").strip()
        if league not in LEAGUES:
            continue
        a, h = split_title(e.get("title"))
        a = a or str(e.get("away") or "").strip()
        h = h or str(e.get("home") or "").strip()
        for side, team in (("awayLogo", a), ("homeLogo", h)):
            if placeholder(team) or e.get(side):
                continue
            logo = resolve(cache, league, team)
            if logo:
                e[side] = logo
                changed += 1
            else:
                unresolved.append({"league": league, "team": team, "title": e.get("title"), "start": e.get("start")})
    feed["events"] = events
    feed.setdefault("repairReport", {})["ncaaLogoAliasesApplied"] = changed
    feed["repairReport"]["ncaaLogoAliasesUnresolved"] = len(unresolved)
    FEED.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"changed": changed, "unresolved": len(unresolved), "unresolved_examples": unresolved[:25]}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
