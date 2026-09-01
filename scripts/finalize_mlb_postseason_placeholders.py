#!/usr/bin/env python3
"""Give MLB postseason placeholder events league-card artwork instead of team logos."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data/schedule_feed.json"
MLB_ART = "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"

PLACEHOLDER_PATTERNS = (
    r"\b(?:AL|NL)\s+(?:LOWER|HIGHER)\s+SEED\b",
    r"\b(?:LOWER|HIGHER)\s+SEED\b",
    r"\b(?:AL|NL)\s+WILD\s+CARD\b",
    r"\b(?:AL|NL)\s+ALL[- ]?STARS\b",
    r"\b(?:AL|NL)\s+(?:#?\d+\s+)?SEED\b",
    r"\b(?:AL|NL)\s+#?\d+\s+SEED\b",
    r"\b(?:AL|NL)\s+\d+\/\d+\s+WINNER\b",
    r"\b(?:AL|NL)\s+WILD\s+CARD\s+#?\d+\b",
    r"\b(?:AL|NL)\s+DIVISION\s+WINNER\b",
    r"\b(?:AL|NL)\s+CHAMPIONSHIP\s+WINNER\b",
    r"\b(?:AL|NL)\s+CHAMPION\b",
    r"\bTBD\b",
    r"\bWINNER\b",
)


def is_placeholder(value: str) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return True
    return any(re.search(pattern, text) for pattern in PLACEHOLDER_PATTERNS)


def main() -> None:
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    changed = 0
    placeholders = 0
    for event in payload.get("events") or []:
        if str(event.get("league") or "").strip() != "MLB":
            continue
        away = str(event.get("away") or "").strip()
        home = str(event.get("home") or "").strip()
        title = str(event.get("title") or "").strip()
        if is_placeholder(away) or is_placeholder(home) or is_placeholder(title):
            placeholders += 1
            before = (event.get("eventType"), event.get("image"), event.get("awayLogo"), event.get("homeLogo"))
            event["eventType"] = "named_event"
            event["leagueArt"] = MLB_ART
            event["image"] = MLB_ART
            event["awayLogo"] = ""
            event["homeLogo"] = ""
            event["mlbPlaceholder"] = True
            event["artworkReason"] = "MLB postseason/placeholder event; team identities not yet determined"
            after = (event.get("eventType"), event.get("image"), event.get("awayLogo"), event.get("homeLogo"))
            changed += before != after
    payload.setdefault("phase3VisualReport", {})["mlbPlaceholderEvents"] = placeholders
    payload["phase3VisualReport"]["mlbPlaceholderEventsUseLeagueArt"] = True
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"MLB placeholder events classified as named_event: {placeholders}; changed={changed}")


if __name__ == "__main__":
    main()
