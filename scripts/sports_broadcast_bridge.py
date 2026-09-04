#!/usr/bin/env python3
"""Bridge authoritative/ESPN broadcast research into the app-facing feed.

This layer discovers *metadata* and legitimate watch/broadcast pages. It never
turns arbitrary web pages into playable streams. A candidate becomes usable for
playback only after normal source/channel validation (including authorized
Xtream matching) accepts it.
"""
from __future__ import annotations
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import sports_web_research as research

FEED = Path("data/schedule_feed.json")
SCHEMA = 1
OFFICIAL_WEIGHT = {"official": 1.0, "espn": 0.92, "discovered": 0.65}

def _host(url: str) -> str:
    return (urllib.parse.urlparse(str(url)).hostname or "").lower()

def _network_hints(row: dict) -> list[str]:
    text = f"{row.get('title','')} {row.get('snippet','')}".lower()
    hints=[]
    for name in ("espn", "espn2", "espn+", "abc", "cbs", "cbs sports", "fox", "fox sports", "nbc", "nbc sports", "tnt", "tbs", "truetv", "usa network", "peacock", "prime video", "apple tv", "youtube"):
        if name in text: hints.append(name)
    return hints

def _candidate(row: dict, kind: str) -> dict:
    authority=str(row.get("authority") or "discovered")
    return {
        "url": str(row.get("url") or ""),
        "host": _host(row.get("url","")),
        "title": str(row.get("title") or "")[:240],
        "snippet": str(row.get("snippet") or "")[:500],
        "authority": authority,
        "score": round(float(row.get("score",0))*OFFICIAL_WEIGHT.get(authority,.65),3),
        "kind": kind,
        "networkHints": _network_hints(row),
        "verifiedForPlayback": False,
        "playbackPolicy": "metadata-only-until-source-validator-accepts",
    }

def _safe_candidates(rows, kind):
    out=[]; seen=set()
    for row in rows:
        url=str(row.get("url") or "").strip(); host=_host(url)
        if not url or url in seen or not host: continue
        # Keep only authoritative/ESPN/legitimate public discovery surfaces.
        authority=str(row.get("authority") or "discovered")
        if authority not in {"official","espn","discovered"}: continue
        seen.add(url); out.append(_candidate(row,kind))
    return sorted(out,key=lambda x:x["score"],reverse=True)[:8]

def build_event_intelligence(event: dict) -> dict:
    league=str(event.get("league") or "").strip(); title=str(event.get("title") or "").strip()
    if not league or not title: return {"schema":SCHEMA,"status":"skipped","reason":"missing league/title"}
    live=research.research_live({"title":title,"league":league,"startUtc":event.get("startUtc") or event.get("start")},limit=10)
    schedule=research.research_schedule(league,{"title":title,"startUtc":event.get("startUtc") or event.get("start")},limit=6)
    livec=_safe_candidates(live,"live"); schedc=_safe_candidates(schedule,"schedule")
    return {"schema":SCHEMA,"generatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"liveCandidates":livec,"scheduleCandidates":schedc,"topLive":livec[0] if livec else None,"topSchedule":schedc[0] if schedc else None}

def run(path: Path = FEED):
    feed=json.loads(path.read_text(encoding="utf-8")); events=feed.get("events") or []
    by_id={}; live_count=0; schedule_count=0
    for event in events:
        if not isinstance(event,dict): continue
        info=build_event_intelligence(event); eid=str(event.get("id") or "")
        if eid: by_id[eid]=info
        live_count += len(info.get("liveCandidates") or [])
        schedule_count += len(info.get("scheduleCandidates") or [])
    feed["sportsBroadcastIntelligence"]={"schema":SCHEMA,"generatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"eventsAnalyzed":len(by_id),"liveCandidates":live_count,"scheduleCandidates":schedule_count,"playbackCandidatesVerified":0}
    feed["sportsBroadcastDetails"]={k:v for k,v in list(by_id.items())[:1000]}
    path.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return feed["sportsBroadcastIntelligence"]

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("feed",nargs="?",default=str(FEED));a=p.parse_args();print(json.dumps(run(Path(a.feed)),indent=2))
