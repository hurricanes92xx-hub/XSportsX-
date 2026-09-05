#!/usr/bin/env python3
"""Apply only validated schedule events returned by Sports Agent tool execution."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import refresh_provider_matrix_v3 as core

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
MEMORY = ROOT / "data" / "sports_brain_memory.json"
SPORT_BY_LEAGUE = {
    "UFC": "mma", "WWE": "wrestling", "AEW": "wrestling", "TNA": "wrestling",
    "AAA Wrestling": "wrestling", "AAA": "wrestling", "Boxing": "boxing",
    "F1": "racing", "MotoGP": "racing", "WRC": "racing", "WEC": "racing", "IMSA": "racing",
}


def valid(event: dict) -> bool:
    if not isinstance(event, dict) or not event.get("title") or not event.get("league"):
        return False
    raw = event.get("startUtc") or event.get("start")
    if not raw:
        return False
    try:
        datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return False
    confidence = float(event.get("discoveryConfidence", 0))
    return confidence >= 0.70 and bool(event.get("scheduleRepair") or event.get("source") in {"official-html", "official-recovery", "google-discovery"})


def main() -> None:
    if not FEED.exists() or not MEMORY.exists():
        print("AI schedule repair bridge: no feed or memory; nothing to apply")
        return
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    memory = json.loads(MEMORY.read_text(encoding="utf-8"))
    agent = memory.get("agent") or {}
    plans = agent.get("lastPlans") or []
    candidates = []
    for plan in plans:
        execution = plan.get("execution") or {}
        for event in execution.get("validatedRecoveredEvents") or []:
            if valid(event):
                event = dict(event)
                event.setdefault("sport", SPORT_BY_LEAGUE.get(str(event.get("league")), "other"))
                candidates.append(event)
    if not candidates:
        payload["aiScheduleRepair"] = {"applied": 0, "inspectedPlans": len(plans), "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
        FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("AI schedule repair bridge: no validated recoveries")
        return
    before = payload.get("events") or []
    canonical, merges, _ = core.dedupe(before + candidates)
    canonical.sort(key=lambda e: e.get("start") or e.get("startUtc") or "")
    payload["events"] = canonical
    counts = {}
    for event in canonical:
        league = str(event.get("league") or "Unknown")
        counts[league] = counts.get(league, 0) + 1
    payload["eventCounts"] = counts
    payload["noEventLeagues"] = [league for league in (payload.get("noEventLeagues") or []) if counts.get(league, 0) == 0]
    payload["identityMergeCount"] = int(payload.get("identityMergeCount", 0)) + merges
    payload["aiScheduleRepair"] = {"applied": len(candidates), "inspectedPlans": len(plans), "identityMerges": merges,
                                    "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                                    "policy": "only validated agent execution results with explicit confidence >= 0.70 enter canonical schedule"}
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"AI schedule repair bridge: applied={len(candidates)}; merges={merges}; total={len(canonical)}")


if __name__ == "__main__":
    main()
