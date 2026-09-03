#!/usr/bin/env python3
"""Reusable league/provider health matrix and automatic promotion."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH_FILE = ROOT / "data" / "provider_health.json"

# Independent providers are deliberately coverage-scoped. They enter the
# matrix only where they can add meaningful redundancy instead of creating
# hundreds of guaranteed-failing calls.
BROAD = {"sportradar", "sportsdataio"}
SPORTMONKS = {"MLS","EPL","UCL","UEL","LaLiga","Serie A","Bundesliga","Ligue 1","NWSL","ICC T20","IPL","F1"}
CFBD = {"NCAA FB"}
MLB_OFFICIAL = {"MLB"}
NHL_OFFICIAL = {"NHL"}
PANDASCORE = {"Esports"}


def _load():
    try:
        value=json.loads(HEALTH_FILE.read_text(encoding="utf-8")); return value if isinstance(value,dict) else {"schema":3,"leagues":{}}
    except Exception: return {"schema":3,"leagues":{}}


def _save(value):
    HEALTH_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=HEALTH_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); tmp.replace(HEALTH_FILE)


def _score(stat):
    attempts=max(1,int(stat.get("attempts",0))); successes=int(stat.get("successes",0)); failures=int(stat.get("consecutiveFailures",0))
    latency=min(5000.0,float(stat.get("lastLatencyMs",5000) or 5000)); events=int(stat.get("lastEventCount",0) or 0)
    return round(max(0.0,(successes/attempts)*70.0+(1.0 if events>0 else 0.0)*20.0+(1.0-latency/5000.0)*10.0-failures*15.0),2)


def record(league,provider,ok,event_count,latency_ms=0,error=""):
    state=_load(); stat=state.setdefault("leagues",{}).setdefault(league,{}).setdefault(provider,{"attempts":0,"successes":0,"consecutiveFailures":0})
    stat["attempts"]=int(stat.get("attempts",0))+1; stat["lastChecked"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    stat["lastEventCount"]=int(event_count or 0); stat["lastLatencyMs"]=round(float(latency_ms or 0),1); stat["lastError"]=str(error or "")[:300]
    if ok and event_count>0: stat["successes"]=int(stat.get("successes",0))+1; stat["consecutiveFailures"]=0
    else: stat["consecutiveFailures"]=int(stat.get("consecutiveFailures",0))+1
    stat["score"]=_score(stat); state["schema"]=3; state["updatedAt"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z"); _save(state)
    return stat


def state(): return _load()


def provider_order(league,configured):
    stats=_load().get("leagues",{}).get(league,{}) ; ranked=[]
    for role,provider in enumerate(configured):
        if provider=="cache": score=-1.0
        else: score=float(stats.get(provider,{}).get("score",50.0))
        ranked.append((score,-role,provider))
    ranked.sort(reverse=True); return [p for _,_,p in ranked]


def build_matrix(league_names,official,dedicated,espn,sportsdb):
    matrix={}
    for league in sorted(set(league_names)):
        candidates=[]
        # Direct league authority gets first opportunity; independent paid data
        # providers supply the next layer, followed by our existing broad feeds.
        if league in MLB_OFFICIAL: candidates += ["mlb-official"]
        elif league in NHL_OFFICIAL: candidates += ["nhl-official"]
        elif league in dedicated: candidates += [dedicated[league]]
        elif league in official: candidates += ["official"]
        if league in BROAD: candidates += ["sportradar","sportsdataio"]
        if league in SPORTMONKS: candidates += ["sportmonks"]
        if league in CFBD: candidates += ["cfbd"]
        if league in PANDASCORE: candidates += ["pandascore"]
        if league in espn: candidates += ["espn"]
        if league in sportsdb: candidates += ["sportsdb"]
        candidates += ["cache"]
        # Keep exactly three live candidates plus cache recovery. Preserve
        # independent sources before lower-quality duplicates.
        live=[]
        for provider in candidates:
            if provider != "cache" and provider not in live: live.append(provider)
        live=live[:3]
        if len(live)<3:
            for provider in ("sportsdb","espn","cache"):
                if provider not in live and (provider=="cache" or provider in sportsdb or provider in espn): live.append(provider)
                if len(live)>=3: break
        configured=live[:3]
        active=provider_order(league,configured)
        matrix[league]={"configured":configured,"activeOrder":active,"primary":active[0] if active else "cache","secondary":active[1] if len(active)>1 else "cache","tertiary":active[2] if len(active)>2 else "cache","cachedRecovery":"cache"}
    return matrix
