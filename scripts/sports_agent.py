#!/usr/bin/env python3
"""Safe autonomous controller for XSportsX sports intelligence.

The controller is model-optional. With an OpenAI-compatible endpoint configured,
it asks the model for a strict JSON plan. Without one, deterministic policy keeps
the system useful. Tool execution is real but bounded to schedule/source discovery,
read-only probing, and safe cache/reconciliation operations; arbitrary code or URLs
are never executed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import provider_discovery as discovery
from sports_knowledge_graph import observe_feed

SCHEMA = 2
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
    source_url: str = ""
    league: str = ""
    start_utc: str = ""


def _safe_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() not in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    except Exception:
        return False


def _probe(url: str) -> dict[str, Any]:
    if not _safe_http_url(url):
        return {"status": "rejected", "reason": "unsafe-url"}
    request = urllib.request.Request(url, headers={"User-Agent": "XSportsX-SportsAgent/1.0", "Accept": "application/json,text/plain,text/html;q=0.8,*/*;q=0.5"}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return {"status": "reachable", "httpStatus": int(response.status), "contentType": str(response.headers.get("Content-Type", ""))[:120]}
    except urllib.error.HTTPError as exc:
        # A 405 means the site rejects HEAD, not that the source is dead. Fall
        # back to a tiny GET while still enforcing a strict response cap.
        if exc.code == 405:
            try:
                get_req = urllib.request.Request(url, headers={"User-Agent": "XSportsX-SportsAgent/1.0", "Range": "bytes=0-4095"}, method="GET")
                with urllib.request.urlopen(get_req, timeout=4) as response:
                    response.read(4096)
                    return {"status": "reachable", "httpStatus": int(response.status), "contentType": str(response.headers.get("Content-Type", ""))[:120], "method": "GET"}
            except Exception as get_exc:
                return {"status": "unreachable", "reason": str(get_exc)[:220]}
        return {"status": "http-error", "httpStatus": exc.code}
    except Exception as exc:
        return {"status": "unreachable", "reason": str(exc)[:220]}


class ToolRegistry:
    """Allowlist of bounded, observable sports operations."""
    def __init__(self) -> None:
        self.tools: dict[str, Callable[[Evidence], dict[str, Any]]] = {
            "refresh_live_evidence": self.refresh_live_evidence,
            "probe_live_state_and_source": self.probe_live_state_and_source,
            "discover_schedule_provider": self.discover_schedule_provider,
            "discover_event_source_metadata": self.discover_event_source_metadata,
            "warm_source": self.warm_source,
            "reconcile_or_archive": self.reconcile_or_archive,
            "refresh_schedule_and_preflight": self.refresh_schedule_and_preflight,
            "defer": lambda e: {"status": "deferred", "reason": e.event_id},
            "no_action": lambda e: {"status": "noop", "reason": e.event_id},
        }

    def execute(self, action: str, evidence: Evidence) -> dict[str, Any]:
        if action not in ALLOWED_ACTIONS or action not in self.tools:
            return {"status": "rejected", "reason": "action_not_allowlisted"}
        return self.tools[action](evidence)

    def discover_schedule_provider(self, e: Evidence) -> dict[str, Any]:
        if not e.league:
            return {"status": "skipped", "reason": "missing-league"}
        candidates = discovery.discover(e.league, max_queries=4)
        promoted = discovery.promote_successful(e.league)
        events = discovery.discovery_events(e.league)
        return {"status": "completed", "league": e.league, "candidates": len(candidates), "promoted": len(promoted), "eventsFound": len(events), "endpoints": [c.get("endpoint") for c in candidates[:8]]}

    def discover_event_source_metadata(self, e: Evidence) -> dict[str, Any]:
        if not e.league:
            return {"status": "skipped", "reason": "missing-league"}
        event = {"title": e.title, "startUtc": e.start_utc}
        candidates = discovery.discover(e.league, event=event, max_queries=3)
        matches = []
        for candidate in candidates:
            for item in candidate.get("events", []) or []:
                if str(item.get("title", "")).strip().lower() == e.title.strip().lower():
                    matches.append({"endpoint": candidate.get("endpoint"), "title": item.get("title"), "startUtc": item.get("startUtc")})
        return {"status": "completed", "league": e.league, "candidates": len(candidates), "eventMatches": matches[:8]}

    def probe_live_state_and_source(self, e: Evidence) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "completed", "eventId": e.event_id, "source": _probe(e.source_url) if e.source_url else {"status": "missing"}}
        if e.phase == "LIVE" and not e.source_url:
            result["sourceDiscovery"] = self.discover_event_source_metadata(e)
        return result

    def refresh_live_evidence(self, e: Evidence) -> dict[str, Any]:
        # Read-only refresh: re-run event-specific discovery when live evidence
        # is weak, then probe any already-known source. No playback is started.
        result = self.probe_live_state_and_source(e)
        result["evidenceRefresh"] = True
        return result

    def warm_source(self, e: Evidence) -> dict[str, Any]:
        # "Warm" is deliberately a connectivity preflight only. It never logs
        # into, downloads, or persists credentials from an Xtream source.
        if not e.source_url:
            return {"status": "skipped", "reason": "missing-source"}
        return {"status": "completed", "preflight": _probe(e.source_url)}

    def reconcile_or_archive(self, e: Evidence) -> dict[str, Any]:
        return {"status": "completed", "decision": "retain" if e.phase in {"LIVE", "UPCOMING", "PREGAME"} else "archive-candidate", "eventId": e.event_id}

    def refresh_schedule_and_preflight(self, e: Evidence) -> dict[str, Any]:
        # Do not recursively invoke the full CI publisher from inside the agent.
        # Instead, perform the bounded pieces that are safe during an agent run.
        discovery_result = self.discover_schedule_provider(e)
        return {"status": "completed", "scheduleDiscovery": discovery_result, "preflight": self.probe_live_state_and_source(e)}


def deterministic_plan(e: Evidence) -> dict[str, Any]:
    action = e.action if e.action in ALLOWED_ACTIONS else "no_action"
    if e.phase == "LIVE" and not e.source_present:
        action = "discover_event_source_metadata"
    elif not e.source_present and e.league:
        action = "discover_schedule_provider"
    return {"action": action, "confidence": max(0.0, min(1.0, e.confidence)), "reason": "; ".join(e.reasons[:4]) or "deterministic policy", "evidenceIds": [e.event_id]}


def model_plan(e: Evidence) -> dict[str, Any] | None:
    endpoint = os.getenv("SPORTS_AGENT_MODEL_URL", "").strip()
    model = os.getenv("SPORTS_AGENT_MODEL", "").strip()
    api_key = os.getenv("SPORTS_AGENT_MODEL_API_KEY", "").strip()
    if not endpoint or not model:
        return None
    prompt = {"task": "Choose one safe next action for a sports event.", "allowedActions": sorted(ALLOWED_ACTIONS), "evidence": {"eventId": e.event_id, "title": e.title, "league": e.league, "startUtc": e.start_utc, "phase": e.phase, "confidence": e.confidence, "actionHint": e.action, "reasons": e.reasons, "provider": e.provider, "sourcePresent": e.source_present}, "outputSchema": {"action": "string", "confidence": "number", "reason": "string", "evidenceIds": "array"}}
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
            source_url=str(event.get("sourceUrl") or ""), league=str(event.get("league") or ""), start_utc=str(event.get("startUtc") or event.get("start") or ""),
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
