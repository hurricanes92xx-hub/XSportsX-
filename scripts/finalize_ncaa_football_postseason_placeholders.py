#!/usr/bin/env python3
"""Classify unresolved NCAA FB/FCS postseason participants as league-art events.

Known school-vs-school games keep team logos. Only games whose participant strings are
clearly unresolved postseason/conference/bowl placeholders are converted to league art.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
ART = {
    "NCAA FB": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png",
    "NCAA FCS": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png",
}
LEAGUES = set(ART)

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9#]+", " ", str(s or "").upper())).strip()

def placeholder(s: str) -> bool:
    n = norm(s)
    if not n:
        return True
    if n in {"TBD", "TBA", "TO BE DETERMINED", "UNKNOWN", "WINNER", "LOSER", "HIGHER SEED", "LOWER SEED"}:
        return True
    if re.search(r"\b(?:CFP|FCS|FBS)?\s*(?:SEED|#?\d+\s*SEED)\b", n):
        return True
    if re.search(r"\b(?:WINNER|LOSER)\b", n):
        return True
    if re.search(r"\b(?:CONFERENCE|BOWL|PLAYOFF|CHAMPIONSHIP)\b", n) and re.search(r"\b(?:TBD|WINNER|SEED|CHAMPION|RUNNER UP|RUNNER-UP)\b", n):
        return True
    return False

def split(title: str):
    for p in (r"^(.+?)\s+@\s+(.+)$", r"^(.+?)\s+AT\s+(.+)$", r"^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$"):
        m = re.match(p, title.strip(), re.I)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", ""

def main() -> None:
    p = json.loads(FEED.read_text(encoding="utf-8"))
    events = p.get("events") or []
    converted = 0
    placeholders = []
    for e in events:
        league = str(e.get("league") or "").strip()
        if league not in LEAGUES:
            continue
        title = str(e.get("title") or "").strip()
        away = str(e.get("away") or "").strip()
        home = str(e.get("home") or "").strip()
        a2, h2 = split(title)
        if a2 and h2:
            away, home = a2, h2
        # Require both sides to be unresolved. A known team must retain its logo.
        if away and home and placeholder(away) and placeholder(home):
            e["eventType"] = "named_event"
            e["ncaaFootballPlaceholder"] = True
            e["postseasonPlaceholder"] = True
            e["image"] = ART[league]
            e["leagueArt"] = ART[league]
            e.pop("awayLogo", None)
            e.pop("homeLogo", None)
            placeholders.append({"league": league, "title": title, "start": e.get("start"), "away": away, "home": home})
            converted += 1
    p.setdefault("ncaaFootballPostseasonReport", {})["placeholderEvents"] = converted
    p["ncaaFootballPostseasonReport"]["leagues"] = sorted(LEAGUES)
    p["ncaaFootballPostseasonReport"]["policy"] = "Only both-sides unresolved postseason/conference/bowl placeholders use NCAA league art; known team participants retain team logos."
    p["ncaaFootballPostseasonReport"]["events"] = placeholders
    FEED.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(p["ncaaFootballPostseasonReport"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
