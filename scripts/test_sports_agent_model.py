#!/usr/bin/env python3
"""Smoke-test configured sports reasoning models without touching production event data."""
from __future__ import annotations
import json, os, urllib.error, urllib.request

ALLOWED = {
    "refresh_live_evidence", "probe_live_state_and_source", "discover_schedule_provider",
    "discover_event_source_metadata", "warm_source", "reconcile_or_archive",
    "refresh_schedule_and_preflight", "defer", "no_action",
}

configs = [
    (os.getenv("SPORTS_AGENT_MODEL_URL", "").strip(), os.getenv("SPORTS_AGENT_MODEL", "").strip(), os.getenv("SPORTS_AGENT_MODEL_API_KEY", "").strip(), "primary"),
    (os.getenv("SPORTS_AGENT_GEMINI_MODEL_URL", "").strip(), os.getenv("SPORTS_AGENT_GEMINI_MODEL", "").strip(), os.getenv("SPORTS_AGENT_GEMINI_API_KEY", "").strip(), "gemini"),
]
configs = [c for c in configs if c[0] and c[1] and c[2]]
if not configs:
    raise SystemExit("MODEL_SMOKE: no configured model; set Groq or Gemini model URL/model/key")

prompt = {
    "task": "Choose the safest useful next sports-intelligence action for this synthetic event. Return JSON only.",
    "allowedActions": sorted(ALLOWED),
    "evidence": {"eventId":"model-smoke-001","title":"Synthetic Test Match","league":"TEST","phase":"PREGAME","confidence":0.50,"sourcePresent":False,"provider":"synthetic"},
    "outputSchema": {"action":"string","confidence":"number","reason":"string","evidenceIds":"array"},
}

errors=[]
for endpoint, model, key, provider in configs:
    body=json.dumps({"model":model,"temperature":0,"messages":[{"role":"system","content":"Return JSON only. Never invent sources. Only choose an allowed action."},{"role":"user","content":json.dumps(prompt)}]}).encode()
    # Groq's Cloudflare edge can reject Python's default urllib signature with 403/1010.
    # Use an explicit application User-Agent and standard Accept header for all compatible providers.
    headers={
        "Content-Type":"application/json",
        "Authorization":f"Bearer {key}",
        "User-Agent":"XSportsX-SportsAgent/1.0",
        "Accept":"application/json",
    }
    req=urllib.request.Request(endpoint,data=body,headers=headers,method="POST")
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            raw=response.read(512*1024).decode("utf-8");status=int(response.status)
        data=json.loads(raw);content=data.get("choices",[{}])[0].get("message",{}).get("content","")
        plan=json.loads(content)
        if not isinstance(plan,dict) or plan.get("action") not in ALLOWED:raise ValueError(f"unsafe/invalid action: {plan!r}")
        confidence=float(plan.get("confidence"))
        if not 0.0<=confidence<=1.0:raise ValueError(f"confidence outside [0,1]: {confidence}")
        print("MODEL_SMOKE: PASS")
        print(json.dumps({"modelSmoke":"PASS","provider":provider,"httpStatus":status,"model":model,"action":plan.get("action"),"confidence":confidence,"reason":str(plan.get("reason",""))[:300]},indent=2))
        raise SystemExit(0)
    except urllib.error.HTTPError as exc:
        detail=exc.read(4096).decode("utf-8",errors="replace");errors.append(f"{provider}: HTTP {exc.code}: {detail[:500]}")
    except Exception as exc:
        errors.append(f"{provider}: {str(exc)[:500]}")

raise SystemExit("MODEL_SMOKE: all configured models failed\n"+"\n".join(errors))
