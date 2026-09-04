#!/usr/bin/env python3
"""Deterministic predictive layer for XSportsX sports intelligence."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
SCHEMA = 2

def _now(): return datetime.now(timezone.utc)
def _parse(value: str):
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception: return None

def _candidate_health(knowledge: dict[str, Any], league: str) -> list[dict[str, Any]]:
    candidates=((knowledge.get("leagues") or {}).get(league) or {}).get("candidates") or []
    ranked=[]
    for c in candidates:
        if not isinstance(c,dict): continue
        success=int(c.get("successes",c.get("observations",0)) or 0); failure=int(c.get("failures",0) or 0)
        latency=float(c.get("latencyMs",0) or 0); confidence=float(c.get("confidence",0) or 0)
        reliability=success/max(1,success+failure); latency_score=1.0 if not latency else max(0.0,min(1.0,1.0-latency/5000.0))
        score=.50*reliability+.30*confidence+.20*latency_score
        ranked.append({"provider":str(c.get("provider") or c.get("name") or c.get("url") or "discovered"),"score":round(score,3),"reliability":round(reliability,3),"confidence":round(confidence,3),"latencyMs":round(latency,1)})
    return sorted(ranked,key=lambda x:x["score"],reverse=True)[:5]

def predict_event(event: dict[str,Any], graph: dict[str,Any], now=None, knowledge: dict[str,Any]|None=None) -> dict[str,Any]:
    now=now or _now(); knowledge=knowledge or {}; start=_parse(event.get("startUtc") or event.get("start"))
    minutes=None if not start else (start-now).total_seconds()/60; source=bool(event.get("sourceUrl") or event.get("youtubeVideoId"))
    phase=str(event.get("intelligencePhase") or "UNKNOWN"); confidence=float(event.get("intelligenceConfidence") or 0)
    providers=_candidate_health(knowledge,str(event.get("league") or "")); risk=.15; reasons=[]
    if not source: risk+=.55; reasons.append("no playable source is currently attached")
    if phase=="LIVE": risk+=.15; reasons.append("event is live")
    if minutes is not None and 0<=minutes<=30: risk+=.15; reasons.append("event starts within 30 minutes")
    if confidence<.6: risk+=.1; reasons.append("live-state confidence is weak")
    if not providers and not source: risk+=.05; reasons.append("no learned provider candidate is currently healthy")
    risk=min(1.0,risk)
    if phase=="LIVE" and not source: action="discover_event_source_metadata"
    elif minutes is not None and 0<=minutes<=15 and not source: action="discover_event_source_metadata"
    elif minutes is not None and 0<=minutes<=30: action="warm_source" if source else "discover_event_source_metadata"
    elif phase in {"LIVE","PREGAME"}: action="refresh_live_evidence"
    else: action="no_action"
    return {"eventId":str(event.get("id","")),"league":str(event.get("league","")),"prediction":"source-at-risk" if risk>=.55 else "ready","risk":round(risk,3),"minutesToStart":None if minutes is None else round(minutes,1),"recommendedAction":action,"confidence":round(max(0.0,min(1.0,1.0-risk*.65)),3),"recommendedProvider":providers[0]["provider"] if providers else "","providerCandidates":providers,"reasons":reasons[:6]}

def run(feed_path:Path,graph_path:Path,output_path:Path|None=None,knowledge_path:Path|None=None)->dict[str,Any]:
    feed=json.loads(feed_path.read_text(encoding="utf-8"))
    try: graph=json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception: graph={"nodes":{},"edges":[]}
    knowledge_path=knowledge_path or Path("data/provider_knowledge.json")
    try: knowledge=json.loads(knowledge_path.read_text(encoding="utf-8"))
    except Exception: knowledge={}
    events=[e for e in (feed.get("events") or []) if isinstance(e,dict)]; predictions=[predict_event(e,graph,knowledge=knowledge) for e in events]
    urgent=[p for p in predictions if p["recommendedAction"]!="no_action"]; provider_choices=sum(1 for p in predictions if p["recommendedProvider"])
    result={"schema":SCHEMA,"generatedAt":_now().replace(microsecond=0).isoformat().replace("+00:00","Z"),"events":len(events),"predictions":len(predictions),"urgent":len(urgent),"sourceRisk":sum(1 for p in predictions if p["prediction"]=="source-at-risk"),"providerChoices":provider_choices}
    feed["sportsPredictions"]=result; feed["sportsPredictionDetails"]=predictions[:1000]
    (output_path or feed_path).write_text(json.dumps(feed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("feed"); p.add_argument("--graph",default="data/sports_knowledge_graph.json"); p.add_argument("--knowledge",default="data/provider_knowledge.json"); args=p.parse_args()
    print(json.dumps(run(Path(args.feed),Path(args.graph),knowledge_path=Path(args.knowledge)),indent=2))
