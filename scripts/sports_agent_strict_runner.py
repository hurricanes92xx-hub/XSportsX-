#!/usr/bin/env python3
"""Run the Sports Agent with the canonical strict operating policy."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sports_agent
from sports_ai_policy import system_prompt


def _strict_call(endpoint, model, key, e):
    prompt = {
        "task": system_prompt(),
        "allowedActions": sorted(sports_agent.ALLOWED_ACTIONS),
        "evidence": {
            "eventId": e.event_id, "title": e.title, "league": e.league,
            "startUtc": e.start_utc, "phase": e.phase,
            "confidence": e.confidence, "actionHint": e.action,
            "reasons": e.reasons, "provider": e.provider,
            "sourcePresent": e.source_present, "correlation": e.correlated,
        },
        "outputSchema": {"action":"string","confidence":"number","reason":"string","evidenceIds":"array"},
    }
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role":"system", "content": system_prompt() + "\nReturn JSON only. Never fabricate."},
            {"role":"user", "content": json.dumps(prompt)},
        ],
    }).encode()
    headers = {
        "Content-Type":"application/json",
        "Authorization":f"Bearer {key}",
        "User-Agent":"XSportsX-SportsAgent/1.0",
        "Accept":"application/json",
    }
    import urllib.request
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=8) as r:
        data = json.loads(r.read(512*1024).decode("utf-8"))
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else ""
    if not content:
        return None
    plan = json.loads(content)
    if not isinstance(plan, dict) or plan.get("action") not in sports_agent.ALLOWED_ACTIONS:
        return None
    plan["confidence"] = max(0, min(1, float(plan.get("confidence", e.confidence))))
    plan["reason"] = str(plan.get("reason", "strict model decision"))[:500]
    plan["evidenceIds"] = [str(x) for x in (plan.get("evidenceIds") or [e.event_id])[:8]]
    return plan


def main():
    p=argparse.ArgumentParser()
    p.add_argument("feed")
    p.add_argument("--memory",default="data/sports_brain_memory.json")
    p.add_argument("--graph",default="data/sports_knowledge_graph.json")
    p.add_argument("--mode",choices=("full","live"),default="full")
    args=p.parse_args()
    original=sports_agent._call_model
    sports_agent._call_model=_strict_call
    try:
        sports_agent.run(Path(args.feed),Path(args.memory),Path(args.graph),mode=args.mode)
    finally:
        sports_agent._call_model=original

if __name__ == "__main__":
    main()
