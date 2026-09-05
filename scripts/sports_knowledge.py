#!/usr/bin/env python3
"""Read-only domain knowledge service for the XSportsX Sports Agent.

Knowledge guides reasoning; it never becomes canonical event truth.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "data" / "sports_knowledge"
FILES = {
    "sports": "sports.json",
    "leagues": "leagues.json",
    "event_types": "event_types.json",
    "lifecycle": "lifecycle_rules.json",
    "broadcast": "broadcast_patterns.json",
    "terminology": "terminology.json",
    "lessons": "learned_lessons.json",
}

@lru_cache(maxsize=16)
def load(name: str) -> dict[str, Any]:
    path = ROOT / FILES[name]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, KeyError):
        return {}


def _match(text: str, aliases: list[str] | tuple[str, ...]) -> bool:
    value = str(text or "").lower()
    return any(alias.lower() in value for alias in aliases)


def identify(event: dict[str, Any]) -> dict[str, Any]:
    sport_text = f"{event.get('sport','')} {event.get('league','')} {event.get('title','')}".lower()
    sports = load("sports").get("sports", {})
    sport_key = "other"
    sport_data: dict[str, Any] = {}
    for key, data in sports.items():
        if _match(sport_text, data.get("aliases", [])) or key.lower() in sport_text:
            sport_key, sport_data = key, data
            break
    leagues = load("leagues").get("leagues", {})
    league_data = leagues.get(str(event.get("league") or ""), {})
    lifecycle = load("lifecycle").get("profiles", {}).get(sport_key, {})
    broadcast = load("broadcast").get("known_patterns", {}).get(str(event.get("league") or ""), {})
    return {
        "sportKey": sport_key,
        "sport": sport_data,
        "league": league_data,
        "lifecycle": lifecycle,
        "broadcast": broadcast,
    }


def reasoning_context(event: dict[str, Any]) -> dict[str, Any]:
    identity = identify(event)
    return {
        "sportKey": identity["sportKey"],
        "sportMechanics": identity["sport"],
        "leagueKnowledge": identity["league"],
        "lifecycleRules": identity["lifecycle"],
        "broadcastKnowledge": identity["broadcast"],
        "terminology": load("terminology").get("terms", {}),
        "learningPolicy": load("lessons").get("policy", {}),
        "trustRule": "Knowledge guides inference only. Official/provider evidence is canonical; never fabricate missing facts.",
    }


def compact_context(event: dict[str, Any]) -> dict[str, Any]:
    ctx = reasoning_context(event)
    return {
        "sportKey": ctx["sportKey"],
        "lifecycleRules": ctx["lifecycleRules"],
        "broadcastKnowledge": ctx["broadcastKnowledge"],
        "leagueKnowledge": ctx["leagueKnowledge"],
        "trustRule": ctx["trustRule"],
    }
