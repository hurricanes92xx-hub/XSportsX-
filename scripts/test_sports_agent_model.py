#!/usr/bin/env python3
"""Smoke-test the configured sports reasoning model without touching production event data."""
from __future__ import annotations
import json, os, urllib.error, urllib.request

ALLOWED = {
    "refresh_live_evidence", "probe_live_state_and_source", "discover_schedule_provider",
    "discover_event_source_metadata", "warm_source", "reconcile_or_archive",
    "refresh_schedule_and_preflight", "defer", "no_action",
}

endpoint = os.getenv("SPORTS_AGENT_MODEL_URL", "").strip()
model = os.getenv("SPORTS_AGENT_MODEL", "").strip()
key = os.getenv("SPORTS_AGENT_MODEL_API_KEY", "").strip()
if not endpoint or not model or not key:
    raise SystemExit("MODEL_SMOKE: missing SPORTS_AGENT_MODEL_URL, SPORTS_AGENT_MODEL, or SPORTS_AGENT_MODEL_API_KEY")

prompt = {
    "task": "Choose the safest useful next sports-intelligence action for this synthetic event. Return JSON only.",
    "allowedActions": sorted(ALLOWED),
    "evidence": {
        "eventId": "model-smoke-001",
        "title": "Synthetic Test Match",
        "league": "TEST",
        "phase": "PREGAME",
        "confidence": 0.50,
        "sourcePresent": False,
        "provider": "synthetic",
    },
    "outputSchema": {"action": "string", "confidence": "number", "reason": "string", "evidenceIds": "array"},
}
body = json.dumps({
    "model": model,
    "temperature": 0,
    "messages": [
        {"role": "system", "content": "Return JSON only. Never invent sources. Only choose an allowed action."},
        {"role": "user", "content": json.dumps(prompt)},
    ],
}).encode()
req = urllib.request.Request(
    endpoint,
    data=body,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(512 * 1024).decode("utf-8")
        status = int(response.status)
except urllib.error.HTTPError as exc:
    detail = exc.read(4096).decode("utf-8", errors="replace")
    raise SystemExit(f"MODEL_SMOKE: HTTP {exc.code}: {detail[:1000]}")
except Exception as exc:
    raise SystemExit(f"MODEL_SMOKE: request failed: {str(exc)[:1000]}")

try:
    data = json.loads(raw)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise ValueError("empty choices[0].message.content")
    plan = json.loads(content)
except Exception as exc:
    raise SystemExit(f"MODEL_SMOKE: invalid model response: {str(exc)[:500]}; raw={raw[:1000]}")

if not isinstance(plan, dict):
    raise SystemExit(f"MODEL_SMOKE: response is not an object: {plan!r}")
if plan.get("action") not in ALLOWED:
    raise SystemExit(f"MODEL_SMOKE: unsafe/invalid action: {plan!r}")
try:
    confidence = float(plan.get("confidence"))
except (TypeError, ValueError):
    raise SystemExit(f"MODEL_SMOKE: confidence is not numeric: {plan!r}")
if not 0.0 <= confidence <= 1.0:
    raise SystemExit(f"MODEL_SMOKE: confidence outside [0,1]: {confidence}")

print("MODEL_SMOKE: PASS")
print(json.dumps({
    "modelSmoke": "PASS",
    "httpStatus": status,
    "model": model,
    "action": plan.get("action"),
    "confidence": confidence,
    "reason": str(plan.get("reason", ""))[:300],
}, indent=2))
