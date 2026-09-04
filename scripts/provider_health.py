#!/usr/bin/env python3
"""Reusable league/provider health matrix and automatic promotion."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HEALTH_FILE=ROOT/"data"/"provider_health.json"
BROAD_LEAGUES={"NFL","CFL","NBA","WNBA","NHL","MLB","MLS","EPL","UCL","UEL","LaLiga","Serie A","Bundesliga","Ligue 1","UFC","F1","IndyCar","PGA","LPGA","LIV Golf","ATP","WTA","PLL","NLL","NASCAR Cup","NASCAR Xfinity","NASCAR Truck","NCAA FB","NCAA BB","NCAA WBB"}
SPORTMONKS_LEAGUES={"MLS","EPL","UCL","UEL","LaLiga","Serie A","Bundesliga","Ligue 1","NWSL","ICC T20","IPL","F1"}
CFBD_LEAGUES={"NCAA FB"}
SPORTSCORE_LEAGUES={"EPL","UCL","UEL","LaLiga","Serie A","Bundesliga","Ligue 1","MLS","NWSL","NBA","WNBA","IPL","ICC T20","ATP","WTA"}
FIVB_LEAGUES={"FIVB Men","FIVB Women"}
DIRECT_LEAGUES={"MLB":"mlb-official","NHL":"nhl-official"}

def _configured(provider):
    if provider=="sportradar": return bool(os.getenv("SPORTRADAR_API_KEY") and os.getenv("SPORTRADAR_ENDPOINT_TEMPLATE"))
    if provider=="sportsdataio": return bool(os.getenv("SPORTSDATAIO_API_KEY") and os.getenv("SPORTSDATAIO_ENDPOINT_TEMPLATE"))
    if provider=="sportmonks": return bool(os.getenv("SPORTMONKS_API_TOKEN") and os.getenv("SPORTMONKS_ENDPOINT_TEMPLATE"))
    if provider=="cfbd": return bool(os.getenv("CFBD_API_KEY"))
    return True

def _load():
    try:
        value=json.loads(HEALTH_FILE.read_text(encoding="utf-8")); return value if isinstance(value,dict) else {"schema":3,"leagues":{}}
    except Exception: return {"schema":3,"leagues":{}}

def _save(value):
    HEALTH_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=HEALTH_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); tmp.replace(HEALTH_FILE)

def _score(stat):
    attempts=max(1,int(stat.get("attempts",0))); successes=int(stat.get("successes",0)); failures=int(stat.get("consecutiveFailures",0)); latency=min(5000.0,float(stat.get("lastLatencyMs",5000) or 5000)); events=int(stat.get("lastEventCount",0) or 0)
    return round(max(0.0,(successes/attempts)*70.0+(1.0 if events>0 else 0.0)*20.0+(1.0-latency/5000.0)*10.0-failures*15.0),2)

def record(league,provider,ok,event_count,latency_ms=0,error=""):
    state=_load(); stat=state.setdefault("leagues",{}).setdefault(league,{}).setdefault(provider,{"attempts":0,"successes":0,"consecutiveFailures":0}); stat["attempts"]=int(stat.get("attempts",0))+1; stat["lastChecked"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"); stat["lastEventCount"]=int(event_count or 0); stat["lastLatencyMs"]=round(float(latency_ms or 0),1); stat["lastError"]=str(error or "")[:300]
    if ok: stat["successes"]=int(stat.get("successes",0))+1; stat["consecutiveFailures"]=0
    else: stat["consecutiveFailures"]=int(stat.get("consecutiveFailures",0))+1
    stat["score"]=_score(stat); state["schema"]=3; state["updatedAt"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"); _save(state); return stat

def state(): return _load()

def provider_order(league,configured):
    stats=_load().get("leagues",{}).get(league,{}); ranked=[]
    for role,provider in enumerate(configured):
        score=-1.0 if provider=="cache" else float(stats.get(provider,{}).get("score",50.0)); ranked.append((score,-role,provider))
    ranked.sort(reverse=True); return [p for _,_,p in ranked]

def build_matrix(league_names,official,dedicated,espn,sportsdb):
    matrix={}
    for league in sorted(set(league_names)):
        candidates=[]
        if league in DIRECT_LEAGUES: candidates.append(DIRECT_LEAGUES[league])
        elif league in dedicated: candidates.append(dedicated[league])
        elif league in official: candidates.append("official")
        if league in BROAD_LEAGUES: candidates += ["sportradar","sportsdataio"]
        if league in SPORTMONKS_LEAGUES: candidates.append("sportmonks")
        if league in CFBD_LEAGUES: candidates.append("cfbd")
        if league in SPORTSCORE_LEAGUES: candidates.append("sportscore")
        if league in FIVB_LEAGUES: candidates.append("fivb")
        if league=="F1": candidates += ["jolpica-f1","openf1"]
        if league=="Bundesliga": candidates.append("openligadb")
        if league in espn: candidates.append("espn")
        if league in sportsdb: candidates.append("sportsdb")
        unique=[]
        for p in candidates:
            if p not in unique: unique.append(p)
        configured=[p for p in unique if p=="cache" or _configured(p)][:5]
        standby=[p for p in unique if p not in configured and p!="cache"]
        active=provider_order(league,configured)
        matrix[league]={"configured":configured,"activeOrder":active,"primary":active[0] if active else "cache","secondary":active[1] if len(active)>1 else "cache","tertiary":active[2] if len(active)>2 else "cache","cachedRecovery":"cache","standbyProviders":standby}
    return matrix
