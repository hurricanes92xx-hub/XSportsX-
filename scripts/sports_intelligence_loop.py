#!/usr/bin/env python3
"""Autonomous cross-sport intelligence loop.

The live sweep is the fast sensor. This layer is the investigator: it audits every
configured league, compares fresh provider evidence with canonical events, researches
gaps/contradictions, asks the model to triage ambiguous cases, validates evidence,
and only then promotes repairs into the canonical feed.
"""
from __future__ import annotations
import argparse,json,os,urllib.error,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any
import refresh_provider_matrix_v3 as matrix_engine
from event_identity import identity_match,merge_event_records,event_identity
import sports_web_research as web_research
import provider_discovery as discovery
import sport_awareness

SCHEMA=1
MODEL_ACTIONS={"promote","research","ignore"}


def now(): return datetime.now(timezone.utc)
def iso(dt): return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def parse_dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None

def is_live(e):
    s=' '.join(str(e.get(k) or '') for k in ('state','status','statusDetail','shortDetail')).lower()
    return any(x in s for x in ('state=in',' in ','live','in progress','inprogress','halftime','q1','q2','q3','q4','period','set','inning')) or str(e.get('state','')).lower()=='in'

def same_day(e, ref):
    d=parse_dt(e.get('startUtc') or e.get('start'))
    return bool(d and (ref-timedelta(hours=8)).date() <= d.date() <= (ref+timedelta(hours=8)).date())

def league_meta(league, officials, icons, espn, ncaa):
    return {'icon':icons.get(league,'🏆'),'espn':espn.get(league),'ncaa':ncaa.get(league)}

def provider_probe(league, matrix, officials, icons, espn, ncaa):
    cfg=matrix.get(league) or {}; order=cfg.get('activeOrder') or cfg.get('configured') or []
    provider=order[0] if order else ''
    if not provider or provider=='cache': return {'league':league,'provider':provider,'ok':False,'events':[],'error':'no-live-provider'}
    try:
        ok,events,error=matrix_engine.fetch(provider,league,league_meta(league,officials,icons,espn,ncaa),officials,[])
        return {'league':league,'provider':provider,'ok':bool(ok),'events':events if isinstance(events,list) else [],'error':str(error or '')[:240]}
    except Exception as exc:
        return {'league':league,'provider':provider,'ok':False,'events':[],'error':f'{type(exc).__name__}: {exc}'[:240]}

def model_configs():
    out=[]
    for u,m,k,label in [('SPORTS_AGENT_MODEL_URL','SPORTS_AGENT_MODEL','SPORTS_AGENT_MODEL_API_KEY','primary'),('SPORTS_AGENT_GEMINI_MODEL_URL','SPORTS_AGENT_GEMINI_MODEL','SPORTS_AGENT_GEMINI_API_KEY','gemini')]:
        if os.getenv(u,'').strip() and os.getenv(m,'').strip() and os.getenv(k,'').strip():out.append((os.getenv(u).strip(),os.getenv(m).strip().rstrip(' .'),os.getenv(k).strip(),label))
    return out

def call_model(case):
    for endpoint,model,key,label in model_configs():
        payload={'model':model,'temperature':0,'messages':[{'role':'system','content':'You are the XSportsX autonomous sports coverage investigator. Return JSON only. Provider/official evidence is factual; never invent. A provider event missing from canonical is a recovery candidate. Prefer PROMOTE only when identity/time is coherent and evidence is authoritative or corroborated. Choose RESEARCH when evidence is incomplete or contradictory. Choose IGNORE only for a clearly stale/invalid record. Use sport-specific lifecycle rules.'},{'role':'user','content':json.dumps(case,ensure_ascii=False)}]}
        try:
            req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':f'Bearer {key}','User-Agent':'XSportsX-IntelligenceLoop/1.0'},method='POST')
            with urllib.request.urlopen(req,timeout=10) as r:data=json.loads(r.read(256*1024).decode())
            content=((data.get('choices') or [{}])[0].get('message') or {}).get('content','')
            plan=json.loads(content)
            if isinstance(plan,dict) and str(plan.get('action','')).lower() in MODEL_ACTIONS:
                plan['action']=str(plan['action']).lower();plan['confidence']=max(0,min(1,float(plan.get('confidence',0))));plan['modelProvider']=label;return plan
        except Exception: continue
    return None

def research_candidate(league,event):
    try:
        rows=web_research.research_schedule(league,{'title':event.get('title',''),'startUtc':event.get('startUtc') or event.get('start')},limit=8)
        extracted=[]
        for row in rows:
            if float(row.get('score',0))<0.70: continue
            body,ctype,_=discovery._get(str(row.get('url','')),timeout=4)
            if body: extracted.extend(discovery._extract_events(body,ctype,league))
        return rows,extracted[:50]
    except Exception as exc:return [],[]

def promote(canonical,candidate,evidence):
    c=dict(candidate);c['aiRecovered']=True;c['intelligenceSource']='autonomous-coverage-audit';c['intelligenceEvidence']=evidence[:8]
    c['id']=event_identity(c.get('league'),c.get('title'),c.get('start') or c.get('startUtc'),c.get('home'),c.get('away'))
    for existing in canonical:
        if identity_match(existing,c):
            merged=merge_event_records(existing,c);existing.clear();existing.update(merged);return False
    canonical.append(c);return True

def audit(feed):
    canonical=[e for e in feed.get('events',[]) if isinstance(e,dict)]
    matrix=feed.get('leagueProviderMatrix') or {}
    leagues=sorted(str(x) for x in matrix if str(x).strip())
    officials=matrix_engine.official_map();icons=matrix_engine.icon_map()
    espn={x[0]:x[1:] for x in matrix_engine.engine.ESPN_LEAGUES};ncaa={x[0]:x[1:] for x in matrix_engine.engine.NCAA_LEAGUES}
    ref=now(); by_league={l:[e for e in canonical if str(e.get('league') or '')==l] for l in leagues}
    probes=[]
    with ThreadPoolExecutor(max_workers=min(12,max(1,len(leagues)))) as pool:
        futs=[pool.submit(provider_probe,l,matrix,officials,icons,espn,ncaa) for l in leagues]
        for f in as_completed(futs): probes.append(f.result())
    probes.sort(key=lambda x:x['league'])
    cases=[]; research_stats={'queries':0,'extracted':0}; promoted=0; rejected=0
    for probe in probes:
        league=probe['league']; local=by_league.get(league,[]); provider_events=probe.get('events') or []
        provider_today=[e for e in provider_events if same_day(e,ref)]
        local_today=[e for e in local if same_day(e,ref)]
        missing=[]
        for pe in provider_today:
            if not any(identity_match(le,pe) for le in local): missing.append(pe)
        local_live=[e for e in local if is_live(e) and same_day(e,ref)]
        provider_live=[e for e in provider_today if is_live(e)]
        suspicious=bool((probe.get('ok') and provider_today and not local_today) or missing or (provider_live and len(provider_live)>len(local_live)))
        if not suspicious: continue
        for pe in missing[:25]:
            sport=sport_awareness.ai_context(pe)
            rows,extracted=research_candidate(league,pe);research_stats['queries']+=len(rows);research_stats['extracted']+=len(extracted)
            corroborated=[x for x in extracted if identity_match(x,pe)]
            official=any(str(r.get('authority'))=='official' and float(r.get('score',0))>=0.70 for r in rows)
            case={'type':'missing-provider-event','league':league,'sportKey':sport['sportKey'],'sportProfile':sport['sportProfile'],'provider':probe['provider'],'candidate':pe,'canonicalCount':len(local),'providerTodayCount':len(provider_today),'providerLiveCount':len(provider_live),'canonicalLiveCount':len(local_live),'research':rows[:6],'corroboratedEvents':corroborated[:6],'officialEvidence':official}
            plan=call_model(case)
            if plan is None:
                if official or corroborated: action='promote';conf=.90 if official else .80
                elif is_live(pe): action='research';conf=.50
                else: action='ignore';conf=.35
                plan={'action':action,'confidence':conf,'reason':'deterministic evidence gate','modelProvider':'none'}
            if plan['action']=='promote' and plan['confidence']>=.78 and (official or corroborated):
                if promote(canonical,pe,[r.get('url','') for r in rows]+['provider:'+probe['provider']]): promoted+=1
            elif plan['action']!='promote': rejected+=1
            cases.append({'league':league,'candidateId':pe.get('id') or event_identity(pe.get('league'),pe.get('title'),pe.get('start') or pe.get('startUtc'),pe.get('home'),pe.get('away')),'candidate':pe,'plan':plan,'researchResults':len(rows),'corroboration':len(corroborated)})
        if probe.get('ok') and not provider_today and not local_today:
            rows,_=research_candidate(league,{'title':league,'startUtc':iso(ref)});research_stats['queries']+=len(rows)
            cases.append({'league':league,'type':'empty-active-league-audit','provider':probe['provider'],'providerOk':True,'researchResults':len(rows),'action':'researched'})
    canonical.sort(key=lambda e:e.get('start') or e.get('startUtc') or '')
    feed['events']=canonical
    feed['intelligenceAudit']={'schema':SCHEMA,'updatedAt':iso(ref),'leaguesAudited':len(leagues),'providerProbes':len(probes),'providerFailures':sum(1 for p in probes if not p.get('ok')),'suspiciousCases':len(cases),'repairsPromoted':promoted,'candidatesRejected':rejected,'research':research_stats,'modelEnabled':bool(model_configs()),'cases':cases[:250]}
    return feed['intelligenceAudit']

def main():
    p=argparse.ArgumentParser();p.add_argument('feed');a=p.parse_args();path=Path(a.feed);feed=json.loads(path.read_text(encoding='utf-8'));print(json.dumps(audit(feed),indent=2));path.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
if __name__=='__main__':main()
