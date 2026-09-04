#!/usr/bin/env python3
"""Safe autonomous controller for XSportsX sports intelligence.

The controller is model-optional. With an OpenAI-compatible endpoint configured,
it asks the model for a strict JSON plan. Without one, a deterministic policy
keeps the system useful and testable. The agent can only choose allowlisted
sports operations; it cannot execute arbitrary shell commands or discovered code.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sports_knowledge_graph import observe_feed

SCHEMA = 1
ALLOWED_ACTIONS = {
    "refresh_live_evidence",
    "probe_live_state_and_source",
    "discover_schedule_provider",
    "discover_event_source_metadata",
    "warm_source",
    "reconcile_or_archive",
    "refresh_schedule_and_preflight",
    "defer",
    "no_action",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Evidence:
    event_id: str
    title: str
    phase: str
    confidence: float
    action: str
    reasons: list[str]
    provider: str
    source_present: bool


class ToolRegistry:
    """Allowlist of operations the agent is permitted to request."""
    def __init__(self) -> None:
        self.tools: dict[str, Callable[[Evidence], dict[str, Any]]] = {
            "refresh_live_evidence": lambda e: {"status": "queued", "reason": e.event_id},
            "probe_live_state_and_source": lambda e: {"status": "queued", "reason": e.event_id},
            "discover_schedule_provider": lambda e: {"status": "queued", "reason": e.title},
            "discover_event_source_metadata": lambda e: {"status": "queued", "reason": e.title},
            "warm_source": lambda e: {"status": "queued", "reason": e.event_id},
            "reconcile_or_archive": lambda e: {"status": "queued", "reason": e.event_id},
            "refresh_schedule_and_preflight": lambda e: {"status": "queued", "reason": e.title},
            "defer": lambda e: {"status": "deferred", "reason": e.event_id},
            "no_action": lambda e: {"status": "noop", "reason": e.event_id},
        }

    def execute(self, action: str, evidence: Evidence) -> dict[str, Any]:
        if action not in ALLOWED_ACTIONS or action not in self.tools:
            return {"status": "rejected", "reason": "action_not_allowlisted"}
        return self.tools[action](evidence)


def deterministic_plan(e: Evidence) -> dict[str, Any]:
    action = e.action if e.action in ALLOWED_ACTIONS else "no_action"
    if e.phase == "LIVE" and not e.source_present:
        action = "discover_event_source_metadata"
    return {
        "action": action,
        "confidence": max(0.0, min(1.0, e.confidence)),
        "reason": "; ".join(e.reasons[:4]) or "deterministic policy",
        "evidenceIds": [e.event_id],
    }


def model_plan(e: Evidence) -> dict[str, Any] | None:
    endpoint = os.getenv("SPORTS_AGENT_MODEL_URL", "").strip()
    model = os.getenv("SPORTS_AGENT_MODEL", "").strip()
    api_key = os.getenv("SPORTS_AGENT_MODEL_API_KEY", "").strip()
    if not endpoint or not model:
        return None
    prompt = {
        "task": "Choose one safe next action for a sports event.",
        "allowedActions": sorted(ALLOWED_ACTIONS),
        "evidence": {"eventId": e.event_id, "title": e.title, "phase": e.phase, "confidence": e.confidence, "actionHint": e.action, "reasons": e.reasons, "provider": e.provider, "sourcePresent": e.source_present},
        "outputSchema": {"action": "string", "confidence": "number", "reason": "string", "evidenceIds": "array"},
    }
    body = json.dumps({"model": model, "temperature": 0, "messages": [{"role": "system", "content": "Return JSON only. Never invent sources. Only choose an allowed action."}, {"role": "user", "content": json.dumps(prompt)}]}).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read(512 * 1024).decode("utf-8")
        data = json.loads(raw)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        plan = json.loads(content)
        if not isinstance(plan, dict) or plan.get("action") not in ALLOWED_ACTIONS:
            return None
        plan["confidence"] = max(0.0, min(1.0, float(plan.get("confidence", e.confidence))))
        plan["reason"] = str(plan.get("reason", "model decision"))[:500]
        ids = plan.get("evidenceIds") or [e.event_id]
        plan["evidenceIds"] = [str(x) for x in ids[:8]]
        return plan
    except (OSError, ValueError, TypeError, KeyError, IndexError, urllib.error.URLError):
        return None


def load_memory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": SCHEMA, "agent": {"runs": 0, "actions": {}, "modelDecisions": 0, "fallbackDecisions": 0}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema": SCHEMA, "agent": {"runs": 0, "actions": {}, "modelDecisions": 0, "fallbackDecisions": 0}}


def run(feed_path: Path, memory_path: Path, graph_path: Path) -> dict[str, Any]:
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    events = feed.get("events") or []
    memory = load_memory(memory_path)
    agent = memory.setdefault("agent", {"runs": 0, "actions": {}, "modelDecisions": 0, "fallbackDecisions": 0})
    registry = ToolRegistry()
    plans: list[dict[str, Any]] = []
    observed = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        observed += 1
        evidence = Evidence(
            event_id=str(event.get("id", "")), title=str(event.get("title", "")),
            phase=str(event.get("intelligencePhase", "UNKNOWN")), confidence=float(event.get("intelligenceConfidence", 0)),
            action=str(event.get("intelligenceAction", "no_action")), reasons=list(event.get("intelligenceReasons") or []),
            provider=str(event.get("provider") or event.get("sourceProvider") or "unknown"),
            source_present=bool(event.get("sourceUrl") or event.get("youtubeVideoId")),
        )
        if evidence.action == "defer" and evidence.phase == "UPCOMING":
            continue
        plan = model_plan(evidence) if evidence.event_id else None
        if plan is not None:
            agent["modelDecisions"] = int(agent.get("modelDecisions", 0)) + 1
        else:
            plan = deterministic_plan(evidence)
            agent["fallbackDecisions"] = int(agent.get("fallbackDecisions", 0)) + 1
        result = registry.execute(str(plan.get("action", "no_action")), evidence)
        action = str(plan.get("action", "no_action"))
        agent["actions"][action] = int(agent["actions"].get(action, 0)) + 1
        plans.append({"eventId": evidence.event_id, "phase": evidence.phase, "plan": plan, "execution": result})

    agent["runs"] = int(agent.get("runs", 0)) + 1
    agent["updatedAt"] = now_iso()
    agent["lastObservedEvents"] = observed
    agent["lastPlans"] = plans[:500]
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    graph_stats = observe_feed(feed, graph_path)
    result = {"schema": SCHEMA, "updatedAt": agent["updatedAt"], "observedEvents": observed, "plans": len(plans), "modelEnabled": bool(os.getenv("SPORTS_AGENT_MODEL_URL") and os.getenv("SPORTS_AGENT_MODEL")), "graph": graph_stats, "actions": agent["actions"]}
    feed["sportsAgent"] = result
    feed_path.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed")
    parser.add_argument("--memory", default="data/sports_brain_memory.json")
    parser.add_argument("--graph", default="data/sports_knowledge_graph.json")
    args = parser.parse_args()
    print(json.dumps(run(Path(args.feed), Path(args.memory), Path(args.graph)), indent=2))


if __name__ == "__main__":
    main()
