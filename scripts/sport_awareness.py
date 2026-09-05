#!/usr/bin/env python3
"""Shared sport profiles plus the static Sports Knowledge Brain.

Knowledge guides inference and model context; explicit provider/official state
always outranks inference. No credentials or playback secrets belong here.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

PROFILES = {
    "soccer": {"aliases": ("soccer", "football", "epl", "mls", "uefa", "fifa"), "pregame": 45, "infer": 30, "duration": 165, "urgent": 90},
    "baseball": {"aliases": ("baseball", "mlb"), "pregame": 45, "infer": 45, "duration": 240, "urgent": 120},
    "basketball": {"aliases": ("basketball", "nba", "wnba", "ncaa basketball"), "pregame": 30, "infer": 35, "duration": 180, "urgent": 90},
    "football": {"aliases": ("football", "nfl", "ncaa football", "college football", "cfl"), "pregame": 60, "infer": 60, "duration": 300, "urgent": 150},
    "hockey": {"aliases": ("hockey", "nhl"), "pregame": 45, "infer": 45, "duration": 240, "urgent": 120},
    "volleyball": {"aliases": ("volleyball", "ncaa women's volleyball", "ncaa volleyball"), "pregame": 30, "infer": 45, "duration": 210, "urgent": 120},
    "tennis": {"aliases": ("tennis", "atp", "wta"), "pregame": 30, "infer": 60, "duration": 360, "urgent": 150},
    "golf": {"aliases": ("golf", "pga", "lpga"), "pregame": 90, "infer": 90, "duration": 600, "urgent": 180},
    "racing": {"aliases": ("racing", "f1", "formula 1", "nascar", "motogp", "imsa", "wec", "wrc"), "pregame": 60, "infer": 90, "duration": 360, "urgent": 180},
    "mma": {"aliases": ("ufc", "mma"), "pregame": 60, "infer": 360, "duration": 360, "urgent": 240},
    "boxing": {"aliases": ("boxing",), "pregame": 60, "infer": 240, "duration": 360, "urgent": 240},
    "wrestling": {"aliases": ("wwe", "aew", "tna", "wrestling", "aaa wrestling", "aaa"), "pregame": 60, "infer": 240, "duration": 300, "urgent": 240},
}
DEFAULT = {"aliases": (), "pregame": 30, "infer": 30, "duration": 180, "urgent": 90}
ROOT = Path(__file__).resolve().parents[1] / "data" / "sports_knowledge"

@lru_cache(maxsize=16)
def knowledge(name: str) -> dict:
    try:
        data = json.loads((ROOT / name).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def profile(sport: str = "", league: str = "", title: str = "") -> tuple[str, dict]:
    text = f"{sport} {league} {title}".lower()
    order = ("mma", "boxing", "wrestling", "racing", "soccer", "football", "baseball", "hockey", "basketball", "volleyball", "tennis", "golf")
    for key in order:
        if any(alias in text for alias in PROFILES[key]["aliases"]): return key, PROFILES[key]
    return "other", DEFAULT

def phase_windows(sport: str = "", league: str = "", title: str = "") -> dict:
    key, p = profile(sport, league, title)
    return {"sportKey": key, "pregameMinutes": p["pregame"], "inferredLiveMinutes": p["infer"], "maxLiveMinutes": p["duration"], "urgentMinutes": p["urgent"]}

def is_urgent(event: dict, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    if str(event.get("intelligencePhase") or "").upper() in {"LIVE", "PREGAME"}: return True
    raw = event.get("startUtc") or event.get("start")
    if not raw: return False
    try: start = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception: return False
    _, p = profile(str(event.get("sport") or ""), str(event.get("league") or ""), str(event.get("title") or ""))
    seconds = (start - now).total_seconds()
    return 0 <= seconds <= p["urgent"] * 60

def ai_context(event: dict) -> dict:
    key, p = profile(str(event.get("sport") or ""), str(event.get("league") or ""), str(event.get("title") or ""))
    leagues = knowledge("leagues.json").get("leagues", {})
    broadcast = knowledge("broadcast_patterns.json").get("known_patterns", {})
    event_types = knowledge("event_types.json")
    terminology = knowledge("terminology.json").get("terms", {})
    return {
        "sportKey": key,
        "sportProfile": {"pregameMinutes": p["pregame"], "inferredLiveMinutes": p["infer"], "maxLiveMinutes": p["duration"], "urgentMinutes": p["urgent"]},
        "leagueKnowledge": leagues.get(str(event.get("league") or ""), {}),
        "broadcastKnowledge": broadcast.get(str(event.get("league") or ""), {}),
        "eventTypeKnowledge": event_types.get("rules", []),
        "statusTerminology": terminology,
        "sportKnowledgeLoaded": True,
        "sportPolicy": "provider/official state outranks timing inference; knowledge only fills reasoning gaps and never invents canonical facts"
    }
