#!/usr/bin/env python3
"""Give non-team sports a named-event presentation with league artwork.

Fight sports, racing, golf, tennis and other individual/non-team competitions must
never be rendered as two team logos. The event title remains the authoritative
competition/event name and the sport/league logo is used as its artwork.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FEED = Path("data/schedule_feed.json")

# Prefer an existing leagueArt value. These fallbacks cover common non-team
# leagues that may not already be present in the visual enrichment map.
NON_TEAM_ART = {
    "UFC": "https://a.espncdn.com/i/teamlogos/leagues/500/ufc.png",
    "Boxing": "https://a.espncdn.com/i/teamlogos/leagues/500/boxing.png",
    "PFL": "https://a.espncdn.com/i/teamlogos/leagues/500/pfl.png",
    "NASCAR": "https://a.espncdn.com/i/teamlogos/leagues/500/nascar.png",
    "NASCAR Cup": "https://a.espncdn.com/i/teamlogos/leagues/500/nascar.png",
    "NASCAR Xfinity": "https://a.espncdn.com/i/teamlogos/leagues/500/nascar.png",
    "NASCAR Truck": "https://a.espncdn.com/i/teamlogos/leagues/500/nascar.png",
    "F1": "https://a.espncdn.com/i/teamlogos/leagues/500/f1.png",
    "Formula 1": "https://a.espncdn.com/i/teamlogos/leagues/500/f1.png",
    "IndyCar": "https://a.espncdn.com/i/teamlogos/leagues/500/indycar.png",
    "MotoGP": "https://a.espncdn.com/i/teamlogos/leagues/500/motogp.png",
    "WEC": "https://a.espncdn.com/i/teamlogos/leagues/500/wec.png",
    "Formula E": "https://a.espncdn.com/i/teamlogos/leagues/500/formula-e.png",
    "NHRA": "https://a.espncdn.com/i/teamlogos/leagues/500/nhra.png",
    "IMSA": "https://a.espncdn.com/i/teamlogos/leagues/500/imsa.png",
    "Supercross": "https://a.espncdn.com/i/teamlogos/leagues/500/supercross.png",
    "ATP": "https://a.espncdn.com/i/teamlogos/leagues/500/atp.png",
    "WTA": "https://a.espncdn.com/i/teamlogos/leagues/500/wta.png",
    "PGA": "https://a.espncdn.com/i/teamlogos/leagues/500/pga.png",
    "LPGA": "https://a.espncdn.com/i/teamlogos/leagues/500/lpga.png",
}

# Explicit league-name matching is intentionally broad so future source naming
# variants such as "UFC Fight Night" or "NASCAR Xfinity Series" are covered.
NON_TEAM_PATTERNS = [
    r"\bUFC\b", r"\bBOXING\b", r"\bPFL\b", r"\bBARE KNUCKLE\b", r"\bBKFC\b",
    r"\bNASCAR\b", r"\bFORMULA\s*1\b", r"\bF1\b", r"\bINDYCAR\b", r"\bMOTOGP\b",
    r"\bWEC\b", r"\bFORMULA\s*E\b", r"\bNHRA\b", r"\bIMSA\b", r"\bSUPERCROSS\b",
    r"\bMOTOCROSS\b", r"\bRACING\b", r"\bGRAND\s+PRIX\b", r"\bATP\b", r"\bWTA\b",
    r"\bPGA\b", r"\bLPGA\b", r"\bGOLF\b", r"\bTENNIS\b", r"\bCYCLING\b",
    r"\bTRACK\s*(?:&|AND)\s*FIELD\b", r"\bATHLETICS\b", r"\bSWIMMING\b", r"\bDIVING\b",
    r"\bGYMNASTICS\b", r"\bFIGURE\s+SKATING\b", r"\bSKIING\b", r"\bSNOWBOARD\b",
    r"\bX\s*GAMES\b", r"\bWRESTLING\b",
]

# For known non-team leagues, these generic ESPN league-art fallbacks are used
# only when phase 3 did not already supply artwork.
KEYWORD_ART = [
    (("UFC", "MMA", "BARE KNUCKLE", "BKFC"), NON_TEAM_ART["UFC"]),
    (("BOXING",), NON_TEAM_ART["Boxing"]),
    (("PFL",), NON_TEAM_ART["PFL"]),
    (("NASCAR",), NON_TEAM_ART["NASCAR"]),
    (("FORMULA 1", "F1"), NON_TEAM_ART["F1"]),
    (("INDYCAR",), NON_TEAM_ART["IndyCar"]),
    (("MOTOGP",), NON_TEAM_ART["MotoGP"]),
    (("WEC",), NON_TEAM_ART["WEC"]),
    (("FORMULA E",), NON_TEAM_ART["Formula E"]),
    (("NHRA",), NON_TEAM_ART["NHRA"]),
    (("IMSA",), NON_TEAM_ART["IMSA"]),
    (("SUPERCROSS", "MOTOCROSS"), NON_TEAM_ART["Supercross"]),
    (("ATP",), NON_TEAM_ART["ATP"]),
    (("WTA",), NON_TEAM_ART["WTA"]),
    (("PGA",), NON_TEAM_ART["PGA"]),
    (("LPGA",), NON_TEAM_ART["LPGA"]),
]


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9&]+", " ", str(value or "").upper())).strip()


def is_non_team_league(league: str) -> bool:
    text = norm(league)
    return any(re.search(pattern, text, re.I) for pattern in NON_TEAM_PATTERNS)


def fallback_art(league: str) -> str:
    text = norm(league)
    for keywords, art in KEYWORD_ART:
        if any(keyword in text for keyword in keywords):
            return art
    return ""


def clean_team_fields(event: dict) -> None:
    # These fields are misleading for an individual/fight/racing event.
    for key in ("awayLogo", "homeLogo", "away", "home"):
        event.pop(key, None)


def main() -> None:
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    changed = 0
    classified = 0
    artwork = 0
    by_league: dict[str, int] = {}

    for event in events:
        league = str(event.get("league") or "").strip()
        if not is_non_team_league(league):
            continue

        classified += 1
        title = str(event.get("title") or "").strip()
        if not title:
            # A non-team event must still have a human-readable event name.
            title = league
            event["title"] = title

        art = str(event.get("leagueArt") or "").strip() or fallback_art(league)
        if art:
            event["leagueArt"] = art
            event["image"] = art
            artwork += 1

        before = (event.get("eventType"), event.get("nonTeamSport"), event.get("image"))
        event["eventType"] = "named_event"
        event["nonTeamSport"] = True
        event["eventName"] = title
        event["sportLogo"] = art
        clean_team_fields(event)
        after = (event.get("eventType"), event.get("nonTeamSport"), event.get("image"))
        if before != after:
            changed += 1
        by_league[league] = by_league.get(league, 0) + 1

    payload["events"] = events
    payload.setdefault("repairReport", {})["nonTeamEventPresentation"] = {
        "classified": classified,
        "artwork_populated": artwork,
        "changed": changed,
        "leagues": by_league,
        "rule": "fight, racing, and individual/non-team sports use the named event title plus sport/league artwork; no team logos",
    }
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"non-team presentation: classified={classified}, artwork={artwork}, changed={changed}")
    print("leagues:", by_league)


if __name__ == "__main__":
    main()
