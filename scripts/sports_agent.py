#!/usr/bin/env python3
"""Safe autonomous controller for XSportsX sports intelligence."""
from __future__ import annotations
import argparse, json, os, urllib.error, urllib.parse, urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import provider_discovery as discovery
from sports_evidence import correlate
from sports_knowledge_graph import observe_feed

SCHEMA = 3
ALLOWED_ACTIONS = {"refresh_live_evidence","probe_live_state_and_source","discover_schedule_provider","discover_event_source_metadata","warm_source","reconcile_or_archive","refresh_schedule_and_preflight","defer","no_action"}

def now_iso(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
@dataclass
class Evidence:
    event_id:str; title:str; phase:str; confidence:float; action:str; reasons:list[str]; provider:str; source_present:bool; source_url:str=''; league:str=''; start_utc:str=''; correlated:dict[str,Any]|None=None

def _safe_http_url(url):
    try:
        p=urllib.parse.urlparse(url); return p.scheme in {'http','https'} and (p.hostname or '').lower() not in {'localhost','127.0.0.1','0.0.0.0','::1'}
    except Exception: return False

def _probe(url):
    if not _safe_http_url(url): return {'status':'rejected','reason':'unsafe-url'}
    req=urllib.request.Request(url,headers={'User-Agent':'XSportsX-SportsAgent/1.0','Accept':'application/json,text/plain,text/html;q=0.8,*/*;q=0.5'},method='HEAD')
    try:
        with urllib.request.urlopen(req,timeout=4) as r: return {'status':'reachable','httpStatus':int(r.status),'contentType':str(r.headers.get('Content-Type',''))[:120]}
    except urllib.error.HTTPError as exc:
        if exc.code==405:
            try:
                q=urllib.request.Request(url,headers={'User-Agent':'XSportsX-SportsAgent/1.0','Range':'bytes=0-4095'},method='GET')
                with urllib.request.urlopen(q,timeout=4) as r: r.read(4096); return {'status':'reachable','httpStatus':int(r.status),'contentType':str(r.headers.get('Content-Type',''))[:120],'method':'GET'}
            except Exception as e: return {'status':'unreachable','reason':str(e)[:220]}
        return {'status':'http-error','httpStatus':exc.code}
    except Exception as e: return {'status':'unreachable','reason':str(e)[:220]}

class ToolRegistry:
    def __init__(self):
        self.tools:dict[str,Callable[[Evidence],dict[str,Any]]]={
            'refresh_live_evidence':self.refresh_live_evidence,'probe_live_state_and_source':self.probe_live_state_and_source,
            'discover_schedule_provider':self.discover_schedule_provider,'discover_event_source_metadata':self.discover_event_source_metadata,
            'warm_source':self.warm_source,'reconcile_or_archive':self.reconcile_or_archive,
            'refresh_schedule_and_preflight':self.refresh_schedule_and_preflight,'defer':lambda e:{'status':'deferred','reason':e.event_id},'no_action':lambda e:{'status':'noop','reason':e.event_id}}
    def execute(self,action,e):
        if action not in ALLOWED_ACTIONS or action not in self.tools: return {'status':'rejected','reason':'action_not_allowlisted'}
        return self.tools[action](e)
    def discover_schedule_provider(self,e):
        if not e.league:return {'status':'skipped','reason':'missing-league'}
        candidates=discovery.discover(e.league,max_queries=4); promoted=discovery.promote_successful(e.league); events=discovery.discovery_events(e.league)
        return {'status':'completed','league':e.league,'candidates':len(candidates),'promoted':len(promoted),'eventsFound':len(events),'endpoints':[c.get('endpoint') for c in candidates[:8]]}
    def discover_event_source_metadata(self,e):
        if not e.league:return {'status':'skipped','reason':'missing-league'}
        candidates=discovery.discover(e.league,event={'title':e.title,'startUtc':e.start_utc},max_queries=3); matches=[]
        for c in candidates:
            for item in c.get('events',[]) or []:
                if str(item.get('title','')).strip().lower()==e.title.strip().lower(): matches.append({'endpoint':c.get('endpoint'),'title':item.get('title'),'startUtc':item.get('startUtc')})
        return {'status':'completed','league':e.league,'candidates':len(candidates),'eventMatches':matches[:8]}
    def probe_live_state_and_source(self,e):
        out={'status':'completed','eventId':e.event_id,'source':_probe(e.source_url) if e.source_url else {'status':'missing'}}
        if e.phase=='LIVE' and not e.source_url: out['sourceDiscovery']=self.discover_event_source_metadata(e)
        return out
    def refresh_live_evidence(self,e): return {'status':'completed','evidenceRefresh':True,'correlation':e.correlated or {},'probe':self.probe_live_state_and_source(e)}
    def warm_source(self,e): return {'status':'skipped','reason':'missing-source'} if not e.source_url else {'status':'completed','preflight':_probe(e.source_url)}
    def reconcile_or_archive(self,e): return {'status':'completed','decision':'retain' if e.phase in {'LIVE','UPCOMING','PREGAME'} else 'archive-candidate','eventId':e.event_id}
    def refresh_schedule_and_preflight(self,e): return {'status':'completed','scheduleDiscovery':self.discover_schedule_provider(e),'preflight':self.probe_live_state_and_source(e)}

def deterministic_plan(e):
    action=e.action if e.action in ALLOWED_ACTIONS else 'no_action'
    c=e.correlated or {}; verdict=str(c.get('verdict',''))
    if verdict=='LIVE' and not e.source_present: action='discover_event_source_metadata'
    elif verdict=='UNCERTAIN': action='refresh_live_evidence'
    elif not e.source_present and e.league: action='discover_schedule_provider'
    return {'action':action,'confidence':max(0,min(1,e.confidence)),'reason':'; '.join(e.reasons[:4]) or 'deterministic policy','evidenceIds':[e.event_id]}

def model_plan(e):
    endpoint=os.getenv('SPORTS_AGENT_MODEL_URL','').strip(); model=os.getenv('SPORTS_AGENT_MODEL','').strip(); key=os.getenv('SPORTS_AGENT_MODEL_API_KEY','').strip()
    if not endpoint or not model:return None
    prompt={'task':'Choose the safest useful next sports-intelligence action. Resolve contradictions conservatively.','allowedActions':sorted(ALLOWED_ACTIONS),'evidence':{'eventId':e.event_id,'title':e.title,'league':e.league,'startUtc':e.start_utc,'phase':e.phase,'confidence':e.confidence,'actionHint':e.action,'reasons':e.reasons,'provider':e.provider,'sourcePresent':e.source_present,'correlation':e.correlated},'outputSchema':{'action':'string','confidence':'number','reason':'string','evidenceIds':'array'}}
    body=json.dumps({'model':model,'temperature':0,'messages':[{'role':'system','content':'Return JSON only. Never invent sources. Only choose an allowed action. Do not override contradictory official evidence without explicit support.'},{'role':'user','content':json.dumps(prompt)}]}).encode(); headers={'Content-Type':'application/json'}
    if key:headers['Authorization']=f'Bearer {key}'
    try:
        with urllib.request.urlopen(urllib.request.Request(endpoint,data=body,headers=headers,method='POST'),timeout=8) as r:data=json.loads(r.read(512*1024).decode('utf-8'))
        plan=json.loads(data.get('choices',[{}])[0].get('message',{}).get('content',''))
        if not isinstance(plan,dict) or plan.get('action') not in ALLOWED_ACTIONS:return None
        plan['confidence']=max(0,min(1,float(plan.get('confidence',e.confidence)))); plan['reason']=str(plan.get('reason','model decision'))[:500]; plan['evidenceIds']=[str(x) for x in (plan.get('evidenceIds') or [e.event_id])[:8]]; return plan
    except (OSError,ValueError,TypeError,KeyError,IndexError,urllib.error.URLError):return None

def load_memory(path):
    try:
        d=json.loads(path.read_text(encoding='utf-8')); return d if isinstance(d,dict) else {}
    except Exception:return {}

def run(feed_path,memory_path,graph_path):
    feed=json.loads(feed_path.read_text(encoding='utf-8')); events=[e for e in feed.get('events',[]) if isinstance(e,dict)]; memory=load_memory(memory_path); agent=memory.setdefault('agent',{'runs':0,'actions':{},'modelDecisions':0,'fallbackDecisions':0}); registry=ToolRegistry(); plans=[]
    for event in events:
        e=Evidence(str(event.get('id','')),str(event.get('title','')),str(event.get('intelligencePhase','UNKNOWN')),float(event.get('intelligenceConfidence',0)),str(event.get('intelligenceAction','no_action')),list(event.get('intelligenceReasons') or []),str(event.get('provider') or event.get('sourceProvider') or 'unknown'),bool(event.get('sourceUrl') or event.get('youtubeVideoId')),str(event.get('sourceUrl') or ''),str(event.get('league') or ''),str(event.get('startUtc') or event.get('start') or ''))
        e.correlated=correlate(event)
        # Hard safety rule: a strong postponed/final verdict cannot be turned into LIVE by the model.
        if e.correlated.get('verdict') in {'FINAL','POSTPONED'} and e.correlated.get('confidence',0)>=0.82: e.action='reconcile_or_archive'; e.phase='FINAL'
        plan=model_plan(e) if e.event_id else None
        if plan is None:plan=deterministic_plan(e);agent['fallbackDecisions']=int(agent.get('fallbackDecisions',0))+1
        else:agent['modelDecisions']=int(agent.get('modelDecisions',0))+1
        result=registry.execute(str(plan.get('action','no_action')),e); action=str(plan.get('action','no_action')); agent['actions'][action]=int(agent['actions'].get(action,0))+1
        plans.append({'eventId':e.event_id,'phase':e.phase,'correlation':e.correlated,'plan':plan,'execution':result})
    agent['runs']=int(agent.get('runs',0))+1; agent['updatedAt']=now_iso(); agent['lastObservedEvents']=len(events); agent['lastPlans']=plans[:500]; memory_path.parent.mkdir(parents=True,exist_ok=True); memory_path.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); graph_stats=observe_feed(feed,graph_path)
    result={'schema':SCHEMA,'updatedAt':agent['updatedAt'],'observedEvents':len(events),'plans':len(plans),'modelEnabled':bool(os.getenv('SPORTS_AGENT_MODEL_URL') and os.getenv('SPORTS_AGENT_MODEL')),'graph':graph_stats,'actions':agent['actions'],'correlatedEvents':len(plans)}; feed['sportsAgent']=result; feed_path.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); return result

def main():
    p=argparse.ArgumentParser();p.add_argument('feed');p.add_argument('--memory',default='data/sports_brain_memory.json');p.add_argument('--graph',default='data/sports_knowledge_graph.json');a=p.parse_args();print(json.dumps(run(Path(a.feed),Path(a.memory),Path(a.graph)),indent=2))
if __name__=='__main__':main()
