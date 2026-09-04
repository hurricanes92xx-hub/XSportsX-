#!/usr/bin/env python3
"""Deterministic predictive layer for XSportsX sports intelligence.

Predicts operational needs (live readiness, source risk, provider choice and
prewarm timing) from current events plus historical provider observations.
It does not predict scores or outcomes; it predicts what the system should do.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1


def _now():
    return datetime.now(timezone.utc)


def _parse(value: str):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _providers(graph: dict[str, Any], league: str) -> list[dict[str, Any]]:
    nodes = graph.get("nodes", {})
    provider_names = []
    for edge in graph.get("edges", []):
        if edge.get("relation") != "belongs_to":
            continue
        event = nodes.get(edge.get("source"), {})
        if event.get("kind") != "event" or edge.get("target") != f"league:{league.strip().lower()}":
            continue
        for e2 in graph.get("edges", []):
            if e2.get("source") == event.get("id") and e2.get("relation") == "provided_by":
                p = nodes.get(e2.get("target"), {})
                if p.get("value"):
                    provider_names.append(p["value"])
    return [{"provider": p, "observations": provider_names.count(p)} for p in sorted(set(provider_names))]


def predict_event(event: dict[str, Any], graph: dict[str, Any], now=None) -> dict[str, Any]:
    now = now or _now()
    start = _parse(event.get("startUtc") or event.get("start"))
    minutes = None if not start else (start - now).total_seconds() / 60
    source = bool(event.get("sourceUrl") or event.get("youtubeVideoId"))
    phase = str(event.get("intelligencePhase") or "UNKNOWN")
    confidence = float(event.get("intelligenceConfidence") or 0)
    risk = 0.15
    reasons = []
    if not source:
        risk += 0.55
        reasons.append("no playable source is currently attached")
    if phase == "LIVE":
        risk += 0.15
        reasons.append("event is live")
    if minutes is not None and 0 <= minutes <= 30:
        risk += 0.15
        reasons.append("event starts within 30 minutes")
    if confidence < 0.6:
        risk += 0.1
        reasons.append("live-state confidence is weak")
    risk = min(1.0, risk)
    if phase == "LIVE" and not source:
        action = "discover_event_source_metadata"
    elif minutes is not None and 0 <= minutes <= 15 and not source:
        action = "discover_event_source_metadata"
    elif minutes is not None and 0 <= minutes <= 30:
        action = "warm_source" if source else "discover_event_source_metadata"
    elif phase in {"LIVE", "PREGAME"}:
        action = "refresh_live_evidence"
    else:
        action = "no_action"
    return {
        "eventId": str(event.get("id", "")),
        "league": str(event.get("league", "")),
        "prediction": "source-at-risk" if risk >= 0.55 else "ready",
        "risk": round(risk, 3),
        "minutesToStart": None if minutes is None else round(minutes, 1),
        "recommendedAction": action,
        "confidence": round(max(0.0, min(1.0, 1.0 - risk * 0.65)), 3),
        "reasons": reasons[:6],
    }


def run(feed_path: Path, graph_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception:
        graph = {"nodes": {}, "edges": []}
    events = [e for e in (feed.get("events") or []) if isinstance(e, dict)]
    predictions = [predict_event(e, graph) for e in events]
    urgent = [p for p in predictions if p["recommendedAction"] != "no_action"]
    result = {"schema": SCHEMA, "generatedAt": _now().replace(microsecond=0).isoformat().replace("+00:00", "Z"), "events": len(events), "predictions": len(predictions), "urgent": len(urgent), "sourceRisk": sum(1 for p in predictions if p["prediction"] == "source-at-risk")}
    feed["sportsPredictions"] = result
    feed["sportsPredictionDetails"] = predictions[:1000]
    target = output_path or feed_path
    target.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("feed")
    p.add_argument("--graph", default="data/sports_knowledge_graph.json")
    args = p.parse_args()
    print(json.dumps(run(Path(args.feed), Path(args.graph)), indent=2))
