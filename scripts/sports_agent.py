#!/usr/bin/env python3
"""Safe autonomous controller for XSportsX sports intelligence.

STRICT SCHEDULE CONTRACT
- Never accept an empty upcoming league as truthful without checking recovery sources.
- Never invent an event, start time, status, source, or broadcast.
- Official/league evidence outranks secondary sources.
- If a configured league has zero canonical events, research it immediately in full mode.
- A successful recovery must be structurally parsed and identity/time validated before merge.
- LIVE/PREGAME source gaps must trigger source research; schedule research and source research
  are separate jobs.
- FINAL/POSTPONED evidence must never be turned back into LIVE/UPCOMING by model output.
"""
from __future__ import annotations
import argparse,json,os,re,urllib.error,urllib.parse,urllib.request
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import provider_discovery as discovery
import sports_web_research as web_research
from sports_evidence import correlate
from sports_knowledge_graph import observe_feed
SCHEMA=4
ALLOWED_ACTIONS={"refresh_live_evidence","probe_live_state_and_source","discover_schedule_provider","discover_event_source_metadata","warm_source","reconcile_or_archive","refresh_schedule_and_preflight","defer","no_action"}
def now_iso():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
@dataclass
class Evidence:
    event_id:str; title:str; phase:str; confidence:float; action:str; reasons:list[str]; provider:str; source_present:bool; source_url:str=''; league:str=''; start_utc:str=''; correlated:dict[str,Any]|None=None
def _safe_http_url(url):
    try:
        p=urllib.parse.urlparse(url);return p.scheme in {'http','https'} and (p.hostname or '').lower() not in {'localhost','127.0.0.1','0.0.0.0','::1'}
    except Exception:return False
def _probe(url):
    if not _safe_http_url(url):return {'status':'rejected','reason':'unsafe-url'}
    req=urllib.request.Request(url,headers={'User-Agent':'XSportsX-SportsAgent/1.0','Accept':'application/json,text/plain,text/html;q=0.8,*/*;q=0.5'},method='HEAD')
    try:
        with urllib.request.urlopen(req,timeout=4) as r:return {'status':'reachable','httpStatus':int(r.status),'contentType':str(r.headers.get('Content-Type',''))[:120]}
    except urllib.error.HTTPError as exc:
        if exc.code==405:
            try:
                q=urllib.request.Request(url,headers={'User-Agent':'XSportsX-SportsAgent/1.0','Range':'bytes=0-4095','Accept':'application/json,text/plain,*/*'},method='GET')
                with urllib.request.urlopen(q,timeout=4) as r:r.read(4096);return {'status':'reachable','httpStatus':int(r.status),'contentType':str(r.headers.get('Content-Type',''))[:120],'method':'GET'}
            except Exception as e:return {'status':'unreachable','reason':str(e)[:220]}
        return {'status':'http-error','httpStatus':exc.code}
    except Exception as e:return {'status':'unreachable','reason':str(e)[:220]}
def _parse_date(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None
def _recover_html_schedule(league,url):
    """Conservative fallback for official pages whose events are rendered as HTML rather than JSON-LD."""
    if league.upper()!='UFC':return []
    body,ctype,_=discovery._get(url,timeout=6)
    if not body:return []
    text=body.decode('utf-8','replace')
    events=[]
    # UFC event cards expose /event/<slug> links. Pair each unique slug with the
    # nearest published start-date text; never synthesize a date from the slug.
    links=list(re.finditer(r'<a[^>]+href=["\']/event/([^"\']+)[^>]*>(.*?)</a>',text,re.I|re.S))
    date_re=re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+([A-Z][a-z]{2})\s+(\d{1,2})\s*/\s*(\d{1,2}:\d{2}\s*[AP]M)\s*([A-Z]{2,5})')
    seen=set()
    for link in links:
        slug=link.group(1); title=re.sub(r'<[^>]+>',' ',link.group(2));title=' '.join(title.split()).strip()
        if not title or slug in seen:continue
        window=text[link.start():min(len(text),link.end()+9000)]
        m=date_re.search(window)
        if not m:continue
        year=datetime.now(timezone.utc).year
        try:
            from email.utils import parsedate_to_datetime
            dt=datetime.strptime(f'{m.group(1)} {m.group(2)} {year} {m.group(3)}', '%b %d %Y %I:%M %p').replace(tzinfo=timezone.utc)
        except Exception:continue
        # UFC pages sometimes expose local ET/EDT/EST. Convert common US zones safely;
        # for other zones, require JSON/ICS/structured recovery instead.
        tz=m.group(4).upper()
        offsets={'UTC':0,'GMT':0,'EST':-5,'EDT':-4,'CST':-6,'CDT':-5,'MST':-7,'MDT':-6,'PST':-8,'PDT':-7}
        if tz not in offsets:continue
        dt=dt.replace(tzinfo=timezone(timedelta(hours=offsets[tz])))
        start=dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
        if start < datetime.now(timezone.utc).isoformat():continue
        events.append({'sport':'MMA','league':league,'title':title,'startUtc':start,'start':start,'status':'scheduled','state':'','source':'official-html','discoveryUrl':url})
        seen.add(slug)
    return events[:50]
class ToolRegistry:
    def __init__(self):
        self.tools={'refresh_live_evidence':self.refresh_live_evidence,'probe_live_state_and_source':self.probe_live_state_and_source,'discover_schedule_provider':self.discover_schedule_provider,'discover_event_source_metadata':self.discover_event_source_metadata,'warm_source':self.warm_source,'reconcile_or_archive':self.reconcile_or_archive,'refresh_schedule_and_preflight':self.refresh_schedule_and_preflight,'defer':lambda e:{'status':'deferred','reason':e.event_id},'no_action':lambda e:{'status':'noop','reason':e.event_id}}
    def execute(self,action,e):
        if action not in ALLOWED_ACTIONS or action not in self.tools:return {'status':'rejected','reason':'action_not_allowlisted'}
        return self.tools[action](e)
    def discover_schedule_provider(self,e):
        if not e.league:return {'status':'skipped','reason':'missing-league'}
        candidates=discovery.discover(e.league,max_queries=4);promoted=discovery.promote_successful(e.league);events=discovery.discovery_events(e.league)
        research=web_research.research_schedule(e.league,{'title':e.title,'startUtc':e.start_utc},limit=8)
        recovered=[]
        for result in research:
            if float(result.get('score',0))<0.70:continue
            body,ctype,_=discovery._get(result.get('url',''),timeout=5)
            if body:recovered.extend(discovery._extract_events(body,ctype,e.league))
            recovered.extend(_recover_html_schedule(e.league,result.get('url','')))
        return {'status':'completed','league':e.league,'candidates':len(candidates),'promoted':len(promoted),'eventsFound':len(events),'googleResearch':research,'validatedRecoveredEvents':recovered[:100],'endpoints':[c.get('endpoint') for c in candidates[:8]]}
    def discover_event_source_metadata(self,e):
        if not e.league:return {'status':'skipped','reason':'missing-league'}
        candidates=discovery.discover(e.league,event={'title':e.title,'startUtc':e.start_utc},max_queries=3);matches=[]
        for c in candidates:
            for item in c.get('events',[]) or []:
                if str(item.get('title','')).strip().lower()==e.title.strip().lower():matches.append({'endpoint':c.get('endpoint'),'title':item.get('title'),'startUtc':item.get('startUtc')})
        live_research=web_research.research_live({'title':e.title,'league':e.league,'startUtc':e.start_utc},limit=10)
        return {'status':'completed','league':e.league,'candidates':len(candidates),'eventMatches':matches[:8],'googleLiveResearch':live_research}
    def probe_live_state_and_source(self,e):
        out={'status':'completed','eventId':e.event_id,'source':_probe(e.source_url) if e.source_url else {'status':'missing'}}
        if e.phase=='LIVE' and not e.source_url:out['sourceDiscovery']=self.discover_event_source_metadata(e)
        return out
    def refresh_live_evidence(self,e):
        probe=self.probe_live_state_and_source(e)
        research=self.discover_event_source_metadata(e) if e.phase in {'LIVE','PREGAME'} or not e.source_present else None
        return {'status':'completed','evidenceRefresh':True,'correlation':e.correlated or {},'probe':probe,'googleLiveResearch':research}
    def warm_source(self,e):return {'status':'skipped','reason':'missing-source'} if not e.source_url else {'status':'completed','preflight':_probe(e.source_url)}
    def reconcile_or_archive(self,e):return {'status':'completed','decision':'retain' if e.phase in {'LIVE','UPCOMING','PREGAME'} else 'archive-candidate','eventId':e.event_id}
    def refresh_schedule_and_preflight(self,e):return {'status':'completed','scheduleDiscovery':self.discover_schedule_provider(e),'preflight':self.probe_live_state_and_source(e)}
def deterministic_plan(e):
    action=e.action if e.action in ALLOWED_ACTIONS else 'no_action';c=e.correlated or {};verdict=str(c.get('verdict',''))
    if (verdict=='LIVE' or e.phase=='LIVE') and not e.source_present:action='discover_event_source_metadata'
    elif verdict=='UNCERTAIN':action='refresh_live_evidence'
    elif not e.source_present and e.league:action='discover_schedule_provider'
    return {'action':action,'confidence':max(0,min(1,e.confidence)),'reason':'; '.join(e.reasons[:4]) or 'deterministic policy','evidenceIds':[e.event_id]}
def _model_configs():
    configs=[]
    primary=(os.getenv('SPORTS_AGENT_MODEL_URL','').strip(),os.getenv('SPORTS_AGENT_MODEL','').strip().rstrip(' .'),os.getenv('SPORTS_AGENT_MODEL_API_KEY','').strip(),'primary')
    gemini=(os.getenv('SPORTS_AGENT_GEMINI_MODEL_URL','').strip(),os.getenv('SPORTS_AGENT_GEMINI_MODEL','').strip().rstrip(' .'),os.getenv('SPORTS_AGENT_GEMINI_API_KEY','').strip(),'gemini')
    for cfg in (primary,gemini):
        if cfg[0] and cfg[1] and cfg[2]:configs.append(cfg)
    return configs
def should_use_model(e):
    if not _model_configs() or not e.event_id:return False
    verdict=str((e.correlated or {}).get('verdict',''))
    if verdict in {'UNCERTAIN','CONTRADICTED'}:return True
    if e.phase in {'LIVE','PREGAME'}:return True
    if not e.source_present and e.confidence<0.75:return True
    return False
def _call_model(endpoint,model,key,e):
    prompt={'task':'Act as a strict sports-data recovery agent. Your job is operational correctness, not conversation. A missing, stale, or contradictory schedule is a failure condition. Choose the safest next action to verify or repair it. NEVER invent an event, time, status, source, broadcast, or provider. OFFICIAL league/promotional evidence outranks secondary evidence. If an active league has no events, choose discover_schedule_provider. If LIVE/PREGAME has no source, choose discover_event_source_metadata. If evidence conflicts, choose refresh_live_evidence. FINAL/POSTPONED is terminal unless stronger explicit evidence proves a change. Do not choose no_action when a required recovery condition exists.','allowedActions':sorted(ALLOWED_ACTIONS),'evidence':{'eventId':e.event_id,'title':e.title,'league':e.league,'startUtc':e.start_utc,'phase':e.phase,'confidence':e.confidence,'actionHint':e.action,'reasons':e.reasons,'provider':e.provider,'sourcePresent':e.source_present,'correlation':e.correlated},'outputSchema':{'action':'string','confidence':'number','reason':'string','evidenceIds':'array'}}
    body=json.dumps({'model':model,'temperature':0,'messages':[{'role':'system','content':'STRICT XSportsX SPORTS INTELLIGENCE POLICY. Return JSON only. Never fabricate. Never suppress a known schedule gap. Never turn an unsupported search result into canonical truth. Follow the action policy exactly.'},{'role':'user','content':json.dumps(prompt)}]}).encode()
    headers={'Content-Type':'application/json','Authorization':f'Bearer {key}','User-Agent':'XSportsX-SportsAgent/1.0','Accept':'application/json'}
    request=urllib.request.Request(endpoint,data=body,headers=headers,method='POST')
    with urllib.request.urlopen(request,timeout=8) as r:data=json.loads(r.read(512*1024).decode('utf-8'))
    plan=json.loads(data.get('choices',[{}])[0].get('message',{}).get('content',''))
    if not isinstance(plan,dict) or plan.get('action') not in ALLOWED_ACTIONS:return None
    plan['confidence']=max(0,min(1,float(plan.get('confidence',e.confidence))));plan['reason']=str(plan.get('reason','model decision'))[:500];plan['evidenceIds']=[str(x) for x in (plan.get('evidenceIds') or [e.event_id])[:8]];return plan
def _mandatory_schedule_gaps(feed):
    events=feed.get('events') or []; counts={}
    for e in events:counts[str(e.get('league') or '')]=counts.get(str(e.get('league') or ''),0)+1
    expected=set(str(x) for x in (feed.get('leagueProviderMatrix') or {}).keys())
    expected|=set(str(x) for x in (feed.get('eventCounts') or {}).keys())
    return sorted(x for x in expected if x and counts.get(x,0)==0)
def _recover_gap(league):
    recovered=[]
    research=web_research.research_schedule(league,limit=10)
    for result in research:
        if float(result.get('score',0))<0.70:continue
        url=result.get('url','');body,ctype,_=discovery._get(url,timeout=5)
        if body:recovered.extend(discovery._extract_events(body,ctype,league))
        recovered.extend(_recover_html_schedule(league,url))
    valid=[];now=datetime.now(timezone.utc)
    for e in recovered:
        start=_parse_date(e.get('startUtc') or e.get('start'))
        if not e.get('title') or not start or start < now-timedelta(hours=12):continue
        e['league']=league;e['source']='ai-web-recovery';e['discoveryConfidence']=0.70;valid.append(e)
    return valid[:100],research
def model_plan(e):
    for endpoint,model,key,_provider in _model_configs():
        try:
            plan=_call_model(endpoint,model,key,e)
            if plan is not None:
                plan['_modelProvider']=_provider;plan['_model']=model
                return plan
        except (OSError,ValueError,TypeError,KeyError,IndexError,urllib.error.URLError):continue
    return None
def load_memory(path):
    try:
        d=json.loads(path.read_text(encoding='utf-8'));return d if isinstance(d,dict) else {}
    except Exception:return {}
def _selected_events(events,mode):
    if mode!='live':return events
    now=datetime.now(timezone.utc);selected=[]
    for event in events:
        phase=str(event.get('intelligencePhase','')).upper();start=str(event.get('startUtc') or event.get('start') or '');urgent=phase in {'LIVE','PREGAME'}
        if not urgent and start:
            try:dt=datetime.fromisoformat(start.replace('Z','+00:00'));urgent=0 <= (dt-now).total_seconds() <= 30*60
            except Exception:pass
        if urgent:selected.append(event)
    return selected
def run(feed_path,memory_path,graph_path,mode='full'):
    feed=json.loads(feed_path.read_text(encoding='utf-8'));events=[e for e in feed.get('events',[]) if isinstance(e,dict)]
    gap_reports=[]
    if mode=='full':
        gaps=_mandatory_schedule_gaps(feed)
        for league in gaps:
            recovered,research=_recover_gap(league);gap_reports.append({'league':league,'researchResults':len(research),'recoveredEvents':len(recovered)})
            if recovered:
                events,merges,_=dedupe_events(events+recovered)
                feed['identityMergeCount']=int(feed.get('identityMergeCount',0))+merges
        feed['events']=events
    events=_selected_events(events,mode);memory=load_memory(memory_path);agent=memory.setdefault('agent',{'runs':0,'actions':{},'modelDecisions':0,'fallbackDecisions':0,'modelProviders':{}});agent.setdefault('actions',{});agent.setdefault('modelDecisions',0);agent.setdefault('fallbackDecisions',0);agent.setdefault('modelProviders',{});registry=ToolRegistry();plans=[]
    for event in events:
        e=Evidence(str(event.get('id','')),str(event.get('title','')),str(event.get('intelligencePhase','UNKNOWN')),float(event.get('intelligenceConfidence',0)),str(event.get('intelligenceAction','no_action')),list(event.get('intelligenceReasons') or []),str(event.get('provider') or event.get('sourceProvider') or 'unknown'),bool(event.get('sourceUrl') or event.get('youtubeVideoId')),str(event.get('sourceUrl') or ''),str(event.get('league') or ''),str(event.get('startUtc') or event.get('start') or ''));e.correlated=correlate(event)
        if e.correlated.get('verdict') in {'FINAL','POSTPONED'} and e.correlated.get('confidence',0)>=0.82:e.action='reconcile_or_archive';e.phase='FINAL'
        plan=model_plan(e) if should_use_model(e) else None
        if plan is None:plan=deterministic_plan(e);agent['fallbackDecisions']=int(agent.get('fallbackDecisions',0))+1
        else:
            agent['modelDecisions']=int(agent.get('modelDecisions',0))+1;provider=str(plan.pop('_modelProvider','primary'));agent.setdefault('modelProviders',{});agent['modelProviders'][provider]=int(agent['modelProviders'].get(provider,0))+1
        # Hard safety gate: model output can never suppress mandatory recovery.
        if (e.correlated or {}).get('verdict') in {'FINAL','POSTPONED'} and (e.correlated or {}).get('confidence',0)>=0.82:plan['action']='reconcile_or_archive'
        elif e.phase in {'LIVE','PREGAME'} and not e.source_present:plan['action']='discover_event_source_metadata'
        elif not e.source_present and e.league and plan.get('action')=='no_action':plan['action']='discover_schedule_provider'
        result=registry.execute(str(plan.get('action','no_action')),e);action=str(plan.get('action','no_action'));agent['actions'][action]=int(agent['actions'].get(action,0))+1;plans.append({'eventId':e.event_id,'phase':e.phase,'correlation':e.correlated,'plan':plan,'execution':result})
    agent['runs']=int(agent.get('runs',0))+1;agent['updatedAt']=now_iso();agent['lastObservedEvents']=len(events);agent['lastMode']=mode;agent['lastPlans']=plans[:500];agent['lastScheduleGapRecovery']=gap_reports;memory_path.parent.mkdir(parents=True,exist_ok=True);memory_path.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');graph_stats=observe_feed(feed,graph_path);result={'schema':SCHEMA,'updatedAt':agent['updatedAt'],'observedEvents':len(events),'plans':len(plans),'mode':mode,'modelEnabled':bool(_model_configs()),'modelDecisions':agent.get('modelDecisions',0),'fallbackDecisions':agent.get('fallbackDecisions',0),'modelProviders':agent.get('modelProviders',{}),'scheduleGapRecovery':gap_reports,'graph':graph_stats,'actions':agent['actions'],'correlatedEvents':len(plans)};feed['sportsAgent']=result;feed_path.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');return result
def dedupe_events(events):
    from event_identity import identity_match,merge_event_records,event_identity
    canonical=[];merges=0
    for raw in events:
        candidate=dict(raw);match=next((i for i,e in enumerate(canonical) if identity_match(e,candidate)),None)
        if match is None:canonical.append(candidate);continue
        merges+=1;canonical[match]=merge_event_records(canonical[match],candidate)
    for e in canonical:e['id']=event_identity(e.get('league'),e.get('title'),e.get('start'),e.get('home'),e.get('away'))
    return canonical,merges,{}
def main():
    p=argparse.ArgumentParser();p.add_argument('feed');p.add_argument('--memory',default='data/sports_brain_memory.json');p.add_argument('--graph',default='data/sports_knowledge_graph.json');p.add_argument('--mode',choices=['full','live'],default='full');a=p.parse_args();print(json.dumps(run(Path(a.feed),Path(a.memory),Path(a.graph),a.mode),indent=2))
if __name__=='__main__':main()
