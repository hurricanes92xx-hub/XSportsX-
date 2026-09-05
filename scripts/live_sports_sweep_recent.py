#!/usr/bin/env python3
"""Production live sweep: UTC-boundary ESPN coverage plus free shadow corroboration."""
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import live_sports_sweep as base
from providers import shadow
from event_identity import identity_match

FEED=Path(__file__).resolve().parents[1]/"data"/"schedule_feed.json"
HEADERS={"User-Agent":"XSportsX-LiveSweep/1.0","Accept":"application/json"}

def _get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=8) as r:return json.loads(r.read().decode("utf-8","ignore"))

def _merge_shadow():
    if not FEED.exists(): return
    payload=json.loads(FEED.read_text(encoding="utf-8")); events=[e for e in (payload.get("events") or []) if isinstance(e,dict)]
    checked=str((payload.get("liveSweep") or {}).get("checkedAtUtc") or datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
    try: rows,failures,counts=shadow.fetch_all()
    except Exception as exc:
        print(f"SHADOW provider layer failed: {type(exc).__name__}: {exc}"); return
    added=0; corroborated=0
    for row in rows:
        if str(row.get("tag") or "").upper()!="LIVE": continue
        match=next((e for e in events if identity_match(e,row)),None)
        evidence={"providerEventId":row.get("providerEventId"),"provider":row.get("source"),"checkedAtUtc":checked}
        if match:
            match.setdefault("liveEvidenceShadow",[]).append(evidence); corroborated+=1; continue
        row=dict(row); row["liveEvidence"]={"providerEventId":row.get("providerEventId"),"provider":row.get("source"),"checkedAtUtc":checked}; row["liveStateSource"]="free-shadow"; row["liveEvidenceShadow"]=[evidence]
        events.append(row); added+=1
    payload["events"]=events; sweep=payload.setdefault("liveSweep",{}); sweep["shadowProviders"]={"enabled":True,"recordCounts":counts,"failures":failures,"liveAdded":added,"liveCorroborated":corroborated}; payload["shadowProviderRecordCounts"]=counts
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"SHADOW LIVE: added={added} corroborated={corroborated} failures={len(failures)}")

def main():
    now=datetime.now(timezone.utc)
    def fetch_league(meta):
        name,sport,league,icon,_days=meta; dates=[(now+timedelta(days=o)).strftime('%Y%m%d') for o in (-1,0,1)]; events=[];last=None
        for day in dates:
            for host in ('https://site.web.api.espn.com','https://site.api.espn.com'):
                url=f'{host}/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={day}&limit=1000'
                try:
                    root=_get_json(url); raw=root.get('events') if isinstance(root,dict) else []
                    if isinstance(raw,list):events.extend(raw)
                    break
                except Exception as exc:last=exc
        seen=set();unique=[]
        for event in events:
            key=str(event.get('id') or event.get('uid') or json.dumps(event,sort_keys=True))
            if key not in seen:seen.add(key);unique.append(event)
        return name,unique,None if unique or not last else str(last)
    def fetch_ncaa(meta):
        name,sport,division,icon=meta; days=[now.date()+timedelta(days=o) for o in (-1,0,1)]; records=[];errors=[]
        for day in days:
            try:
                root=base._fetch_scoreboard_day(sport,division,day)
                if root:
                    for game in __import__('providers.ncaa',fromlist=['_walk_games'])._walk_games(root):
                        event=base._normalize(game,name,icon)
                        if event:records.append(event)
            except Exception as exc:errors.append(f'primary:{exc}')
            try:records.extend(base._fetch_espn_day(name,day))
            except Exception as exc:errors.append(f'espn:{exc}')
        seen=set();out=[]
        for event in records:
            key=(str(event.get('away') or '').lower(),str(event.get('home') or '').lower(),str(event.get('start') or event.get('startUtc') or ''),str(event.get('providerEventId') or ''))
            if key not in seen:seen.add(key);out.append(event)
        return name,out,None if out or not errors else '; '.join(errors)
    base._fetch_league=fetch_league; base._fetch_ncaa=fetch_ncaa; base.main(); _merge_shadow()

if __name__=='__main__':main()
