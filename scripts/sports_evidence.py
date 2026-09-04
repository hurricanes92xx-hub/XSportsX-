#!/usr/bin/env python3
"""Deterministic multi-source evidence correlation for Sports Agent decisions.

The model may reason over this evidence, but strong contradictory local/official
signals are never silently discarded. This module is deliberately dependency-free.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_WEIGHTS = {
    "official": 1.00,
    "fivb-vis": 0.98,
    "mlb-official": 0.98,
    "nhl-official": 0.98,
    "nfl-official": 0.98,
    "ncaa": 0.96,
    "espn": 0.90,
    "espn-ncaa": 0.90,
    "espn-shadow": 0.82,
    "openf1": 0.90,
    "jolpica-f1": 0.88,
    "openligadb": 0.82,
    "sportsdb": 0.70,
    "discovery": 0.62,
    "cache": 0.55,
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("@", " vs ").split())


def _provider(event: dict[str, Any]) -> str:
    return str(event.get("provider") or event.get("sourceProvider") or event.get("source") or "unknown").lower()


def _status(event: dict[str, Any]) -> str:
    return _norm(event.get("status") or event.get("state"))


def _is_live(event: dict[str, Any]) -> bool:
    return _status(event) in {"live", "in progress", "in-progress", "playing", "1h", "2h", "3h"} or str(event.get("intelligencePhase", "")).upper() == "LIVE"


def _is_final(event: dict[str, Any]) -> bool:
    return _status(event) in {"final", "finished", "complete", "completed", "ft", "closed"} or str(event.get("intelligencePhase", "")).upper() == "FINAL"


def _is_postponed(event: dict[str, Any]) -> bool:
    return any(x in _status(event) for x in ("postponed", "canceled", "cancelled", "suspended", "abandoned"))


def correlate(event: dict[str, Any], related: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Correlate evidence for one canonical event and return an explainable verdict."""
    peers = [x for x in (related or []) if isinstance(x, dict)]
    all_events = [event] + peers
    signals: list[dict[str, Any]] = []
    live_weight = final_weight = postponed_weight = 0.0
    seen_providers: set[str] = set()
    for item in all_events:
        provider = _provider(item)
        if provider in seen_providers:
            continue
        seen_providers.add(provider)
        weight = SOURCE_WEIGHTS.get(provider, 0.50)
        if item.get("sourceUrl") or item.get("youtubeVideoId"):
            weight *= 1.03
        state = "LIVE" if _is_live(item) else "FINAL" if _is_final(item) else "POSTPONED" if _is_postponed(item) else "SCHEDULED"
        signals.append({"provider": provider, "state": state, "weight": round(weight, 3), "title": str(item.get("title") or "")[:160]})
        if state == "LIVE": live_weight += weight
        elif state == "FINAL": final_weight += weight
        elif state == "POSTPONED": postponed_weight += weight

    total = live_weight + final_weight + postponed_weight
    reasons: list[str] = []
    if live_weight and final_weight:
        reasons.append("live/final contradiction across providers")
    if live_weight and postponed_weight:
        reasons.append("live/postponed contradiction across providers")
    if live_weight >= 0.90 and live_weight > final_weight and live_weight > postponed_weight:
        verdict = "LIVE"
        confidence = min(0.99, 0.72 + min(0.24, live_weight / 4.0))
        reasons.append("independent live evidence agrees")
    elif postponed_weight >= 0.90 and postponed_weight >= live_weight:
        verdict = "POSTPONED"
        confidence = min(0.99, 0.76 + min(0.20, postponed_weight / 4.0))
        reasons.append("provider evidence indicates postponement/cancellation")
    elif final_weight >= 0.90 and final_weight >= live_weight:
        verdict = "FINAL"
        confidence = min(0.99, 0.76 + min(0.20, final_weight / 4.0))
        reasons.append("provider evidence agrees event is final")
    else:
        verdict = "UNCERTAIN"
        confidence = 0.35 if total == 0 else min(0.78, 0.45 + max(live_weight, final_weight, postponed_weight) / 4.0)
        reasons.append("insufficient independent agreement")

    if not reasons:
        reasons.append("no decisive evidence")
    return {
        "schema": 1,
        "eventId": str(event.get("id") or ""),
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "signals": signals,
        "reasons": reasons[:6],
        "independentProviders": len(seen_providers),
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def attach(feed: dict[str, Any]) -> dict[str, Any]:
    """Attach evidence verdicts to a feed without changing canonical events."""
    events = [e for e in (feed.get("events") or []) if isinstance(e, dict)]
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in events:
        key = (_norm(e.get("league")), _norm(e.get("title")))
        by_key.setdefault(key, []).append(e)
    reports = []
    for e in events:
        key = (_norm(e.get("league")), _norm(e.get("title")))
        reports.append(correlate(e, by_key.get(key, [])[1:]))
    feed["sportsEvidence"] = {"schema": 1, "events": reports, "updatedAt": reports[-1]["updatedAt"] if reports else datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
    return feed
