#!/usr/bin/env python3
"""Validate provider/live-state data before publishing the canonical feed."""
from __future__ import annotations
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FEED=ROOT/"data"/"schedule_feed.json"
REPORT=ROOT/"data"/"provider_health_gate.json"

def parse_dt(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:return None

def is_live(event):
    return str(event.get("tag","")).upper()=="LIVE" or str(event.get("status","")).upper()=="LIVE" or str(event.get("state","")).lower()=="in"

def set_upcoming(event,reason):
    event.update({"tag":"UPCOMING","status":"UPCOMING","state":"pre","liveStateSource":"provider-health-gate","liveStateRejectedReason":reason})
    event.pop("liveEvidence",None)

def main():
    if not FEED.exists():raise SystemExit("provider health gate: missing schedule_feed.json")
    payload=json.loads(FEED.read_text(encoding="utf-8"));events=[e for e in (payload.get("events") or []) if isinstance(e,dict)];now=datetime.now(timezone.utc);future_live=[];missing_start=[];stale_evidence=[]
    sweep=payload.get("liveSweep") or {};checked_at=str(sweep.get("checkedAtUtc") or "")
    for event in events:
        if not is_live(event):continue
        evidence=event.get("liveEvidence") or {}
        if not evidence.get("providerEventId") or str(evidence.get("checkedAtUtc") or "") != checked_at:
            stale_evidence.append({"league":event.get("league"),"title":event.get("title"),"reason":"missing-or-stale-provider-evidence"});set_upcoming(event,"missing-or-stale-provider-evidence");continue
        start=parse_dt(event.get("startUtc") or event.get("start"))
        if start and start>now+timedelta(minutes=2):
            future_live.append({"league":event.get("league"),"title":event.get("title"),"startUtc":event.get("startUtc") or event.get("start")});set_upcoming(event,"provider-live-starts-too-far-in-future")
        elif not start:
            # A provider-confirmed LIVE state is stronger than a missing clock.
            # Do not turn a game that is actually in progress into UPCOMING just
            # because the provider omitted its scheduled start timestamp.
            missing_start.append({"league":event.get("league"),"title":event.get("title"),"reason":"missing_start_provider_confirmed"})
    report={"schema":3,"checkedAtUtc":now.isoformat().replace("+00:00","Z"),"eventCount":len(events),"futureLiveCorrected":len(future_live),"missingStartLiveCorrected":0,"missingStartLiveWarnings":len(missing_start),"staleLiveEvidenceCorrected":len(stale_evidence),"providerFailures":payload.get("providerFailures") or payload.get("failedSources") or [],"failedLiveStates":future_live+stale_evidence,"liveWarnings":missing_start}
    payload["events"]=events;payload["providerHealthGate"]=report;FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps(report,indent=2))
    remaining=[e for e in events if is_live(e)]
    if any(not (e.get("liveEvidence") or {}).get("providerEventId") for e in remaining):raise SystemExit("provider health gate: unevidenced LIVE event remains")
    impossible=[e for e in remaining if (lambda d:d is not None and d>now+timedelta(minutes=2))(parse_dt(e.get("startUtc") or e.get("start")))]
    if impossible:raise SystemExit(f"provider health gate: {len(impossible)} impossible future LIVE events remain")
if __name__=="__main__":main()
