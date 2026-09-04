#!/usr/bin/env python3
"""Bridge authoritative/ESPN broadcast research into the app-facing feed.

This discovers broadcast metadata only. It never converts arbitrary pages into
playable streams; the normal source/channel validator must accept a source.
"""
from __future__ import annotations
import json, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import sports_web_research as research

FEED=Path("data/schedule_feed.json"); SCHEMA=1
OFFICIAL_WEIGHT={"official":1.0,"espn":.92,"discovered":.65}

def _host(url): return (urllib.parse.urlparse(str(url)).hostname or "").lower()
def _candidate(row,kind):
    authority=str(row.get("authority") or "discovered")
    text=f"{row.get('title','')} {row.get('snippet','')}".lower()
    hints=[x for x in ("espn","espn2","espn+","abc","cbs","cbs sports","fox","fox sports","nbc","nbc sports","tnt","tbs","truetv","usa network","peacock","prime video","apple tv","youtube") if x in text]
    return {"url":str(row.get("url") or ""),"host":_host(row.get("url","")),"title":str(row.get("title") or "")[:240],"snippet":str(row.get("snippet") or "")[:500],"authority":authority,"score":round(float(row.get("score",0))*OFFICIAL_WEIGHT.get(authority,.65),3),"kind":kind,"networkHints":hints,"verifiedForPlayback":False,"playbackPolicy":"metadata-only-until-source-validator-accepts"}

def _safe(rows,kind):
    out=[];seen=set()
    for row in rows:
        url=str(row.get("url") or "").strip();host=_host(url);authority=str(row.get("authority") or "discovered")
        if not url or not host or url in seen or authority not in {"official","espn","discovered"}: continue
        seen.add(url);out.append(_candidate(row,kind))
    return sorted(out,key=lambda x:x["score"],reverse=True)[:8]

def build_event_intelligence(event):
    league=str(event.get("league") or "").strip();title=str(event.get("title") or "").strip()
    if not league or not title:return {"schema":SCHEMA,"status":"skipped","reason":"missing league/title"}
    e={"title":title,"league":league,"startUtc":event.get("startUtc") or event.get("start")}
    live=_safe(research.research_live(e,limit=8),"live")
    sched=_safe(research.research_schedule(league,e,limit=5),"schedule")
    return {"schema":SCHEMA,"generatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"liveCandidates":live,"scheduleCandidates":sched,"topLive":live[0] if live else None,"topSchedule":sched[0] if sched else None}

def run(path=FEED):
    feed=json.loads(path.read_text(encoding="utf-8"));events=feed.get("events") or [];now=datetime.now(timezone.utc)
    selected=[]
    for event in events:
        if not isinstance(event,dict):continue
        phase=str(event.get("intelligencePhase") or "")
        try:start=datetime.fromisoformat(str(event.get("startUtc") or event.get("start")).replace("Z","+00:00"))
        except Exception:start=None
        minutes=None if not start else (start-now).total_seconds()/60
        needs_source=not bool(event.get("sourceUrl") or event.get("youtubeVideoId"))
        if phase in {"LIVE","PREGAME"} or (needs_source and minutes is not None and 0<=minutes<=90): selected.append(event)
    details={};live_count=0;schedule_count=0
    for event in selected:
        info=build_event_intelligence(event);eid=str(event.get("id") or "")
        if eid:details[eid]=info
        live_count+=len(info.get("liveCandidates") or []);schedule_count+=len(info.get("scheduleCandidates") or [])
    result={"schema":SCHEMA,"generatedAt":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"eventsAnalyzed":len(details),"liveCandidates":live_count,"scheduleCandidates":schedule_count,"playbackCandidatesVerified":0,"selectionPolicy":"LIVE/PREGAME plus source gaps within 90 minutes"}
    feed["sportsBroadcastIntelligence"]=result;feed["sportsBroadcastDetails"]={k:v for k,v in list(details.items())[:1000]}
    path.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");return result

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("feed",nargs="?",default=str(FEED));a=p.parse_args();print(json.dumps(run(Path(a.feed)),indent=2))
