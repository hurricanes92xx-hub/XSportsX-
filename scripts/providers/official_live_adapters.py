#!/usr/bin/env python3
"""Dedicated official live adapters for FIVB and NASCAR."""
from __future__ import annotations
import json, re, urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; FEED=ROOT/'data'/'schedule_feed.json'; UA='XSportsX-OfficialLiveAdapters/2.0'
FIVB_URL='https://www.fivb.org/Vis2009/XmlRequest.asmx'

def _get_bytes(url,timeout=12):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/xml,text/xml,*/*'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def _post_xml(xml,timeout=12):
 req=urllib.request.Request(FIVB_URL,data=xml.encode(),headers={'User-Agent':UA,'Accept':'application/xml,text/xml,*/*','Content-Type':'text/xml; charset=utf-8'},method='POST')
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def _iso(v):
 if not v:return ''
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except:return ''
def _field(el,*names):
 wanted={x.lower() for x in names}
 for k,v in el.attrib.items():
  if k.lower() in wanted and str(v).strip():return str(v).strip()
 for n in el.iter():
  if n is el:continue
  if n.tag.split('}')[-1].lower() in wanted and n.text and n.text.strip():return n.text.strip()
 return ''
def _norm(v):return ''.join(c.lower() for c in str(v or '') if c.isalnum())
LIVE_STATUS_NUM={5,8,11,14,17,20,23};LIVE_STATUS_NAMES={f'inset{i}' for i in range(1,8)}
def _is_live(v):
 s=_norm(v)
 try:return int(str(v).strip()) in LIVE_STATUS_NUM
 except:return s in LIVE_STATUS_NAMES
def _fivb_records(root):
 return [e for e in root.iter() if e.tag.split('}')[-1].lower() in {'volleyballmatch','volleymatch','match'} and _field(e,'No','NoMatch','NoVolleyMatch').isdigit()]
def _parse_live(raw):
 try:
  root=ET.fromstring(raw);tags={e.tag.split('}')[-1].lower() for e in root.iter()}
  if {'matchlive','volleylive'} & tags:return True,'live',root
  if {'nochanges','notmodified'} & tags:return True,'unchanged',root
  errs=[]
  for e in root.iter():
   tag=e.tag.split('}')[-1]
   if 'error' in e.tag.lower() or tag.lower() in {'badparameter','parametermissing','notinnewformat','nodata'}:
    detail=_field(e,'Code','code','Text','Message','message','Parameter') or (e.text or '').strip()
    ident=_field(e,'Id','id')
    errs.append(f'{tag}:{ident}:{detail}'.rstrip(':'))
  return False,'response:'+(';'.join(errs) or ','.join(sorted(tags)) or 'empty'),root
 except Exception as e:return False,f'parse:{type(e).__name__}',None

def _fivb_probe(no,typ='GetVolleyLive',param='NoMatch',options=128):
 no=int(no)
 xml=f'<Requests><Request Type="{typ}" {param}="{no}" Options="{options}" Version="0" /></Requests>'
 try:
  raw=_post_xml(xml);ok,why,_=_parse_live(raw);return ok,f'POST:wrapped:{typ}:{param}:{options}:{why}'
 except urllib.error.HTTPError as e:
  b=e.read().decode('utf-8','replace')[:1000];return False,f'POST:wrapped:{typ}:{param}:{options}:http={e.code}:{b}'
 except Exception as e:return False,f'POST:wrapped:{typ}:{param}:{options}:{type(e).__name__}:{str(e)[:160]}'

def _fivb_live_request(no):
 # GetVolleyLive became a normal request and can be included in <Requests>.
 # Probe the legacy documented volleyball contract first, then the newer GetMatchLive contract.
 probes=[
  ('GetVolleyLive','NoMatch',128),
  ('GetVolleyLive','NoMatch',0),
  ('GetMatchLive','NoVolleyMatch',128),
  ('GetMatchLive','NoVolleyMatch',0),
 ]
 diagnostics=[]
 for typ,param,opt in probes:
  ok,why=_fivb_probe(no,typ,param,opt);diagnostics.append(why)
  if ok:return True,why
  # A contract error is enough to reject this probe; do not hammer the match.
 return False,' | '.join(diagnostics)

def _fivb():
 result=[];d={'status':'ok','listRecords':0,'candidates':0,'liveVerified':0,'liveRejected':0,'errors':[],'verification':{}}
 req='<Request Type="GetVolleyMatchList" Fields="No DateTimeUtc BeginDateTimeUtc TeamNameA TeamNameB Status Gender TournamentName HasLiveData"><Filter ForLiveScore="true" /></Request>'
 try:root=ET.fromstring(_post_xml(req))
 except Exception as e:d['status']='unavailable';d['errors'].append(f'list:{type(e).__name__}:{str(e)[:300]}');return result,d
 records=_fivb_records(root);d['listRecords']=len(records);candidates=[]
 for el in records:
  no=_field(el,'No','NoMatch','NoVolleyMatch');status=_field(el,'Status','StatusName','MatchStatus')
  if _is_live(status):candidates.append((el,no))
 d['candidates']=len(candidates)
 if not candidates:return result,d
 smoke_el,smoke_no=candidates[0];ok,why=_fivb_live_request(smoke_no);d['verification'][str(smoke_no)]=why
 if not ok:
  d['status']='contract-failed';d['errors'].append(why);d['liveRejected']=len(candidates);return result,d
 for el,no in candidates:
  if str(no)!=str(smoke_no):
   ok,why=_fivb_live_request(no);d['verification'][str(no)]=why
   if not ok:d['liveRejected']+=1;continue
  home=_field(el,'TeamNameA','TeamAName','NameA','TeamA');away=_field(el,'TeamNameB','TeamBName','NameB','TeamB');start=_iso(_field(el,'DateTimeUtc','BeginDateTimeUtc','DateUtc'));gender=_norm(_field(el,'Gender','TournamentGender'));tournament=_field(el,'TournamentName','Name');league='FIVB Women' if gender in {'w','women','female','f'} or 'women' in _norm(tournament) else 'FIVB Men'
  result.append({'league':league,'title':f'{away} @ {home}' if away and home else f'FIVB Match {no}','start':start,'startUtc':start,'tag':'LIVE','status':'LIVE','state':'in','home':home,'away':away,'source':'fivb-vis-official','providerEventId':f'fivb:{no}','liveEvidenceSource':'fivb-vis'});d['liveVerified']+=1
 return result,d

def _nascar():
 result=[];d={'status':'ok','liveFeed':False,'liveVerified':0,'errors':[]}
 for v in ('1','2'):
  try:
   req=urllib.request.Request(f'https://feed.nascar.com/api/LiveFeed?v={v}',headers={'User-Agent':UA,'Referer':'https://www.nascar.com/','Origin':'https://www.nascar.com'})
   with urllib.request.urlopen(req,timeout=10) as r:x=json.loads(r.read().decode('utf-8','ignore'))
   d['liveFeed']=True
   for z in x if isinstance(x,list) else [x]:
    if not isinstance(z,dict) or str(z.get('series_id') or z.get('seriesId'))!='3':continue
    rid=z.get('race_id') or z.get('raceId') or z.get('run_id');nm=z.get('run_name') or z.get('event_name') or 'NASCAR Craftsman Truck Series';st=_iso(z.get('time_of_day_os') or z.get('start_time_utc') or z.get('start_time'));result.append({'league':'NASCAR Truck','title':nm,'start':st,'startUtc':st,'tag':'LIVE','status':'LIVE','state':'in','source':'nascar-livefeed-official','providerEventId':f'nascar:live:{rid}','liveEvidenceSource':'nascar-livefeed'});d['liveVerified']+=1
   if result:return result,d
   break
  except Exception as e:d['errors'].append(f'livefeed:{type(e).__name__}')
 d['status']='blocked' if d['errors'] and not d['liveFeed'] else 'no-live';return result,d

def main():
 if not FEED.exists():raise SystemExit('official adapters: missing schedule_feed.json')
 payload=json.loads(FEED.read_text());events=[e for e in payload.get('events',[]) if isinstance(e,dict)];checked=str((payload.get('liveSweep') or {}).get('checkedAtUtc') or datetime.now(timezone.utc).isoformat().replace('+00:00','Z'));diagnostics={};added=corroborated=0
 for name,fn in (('FIVB',_fivb),('NASCAR Truck',_nascar)):
  rows,diag=fn();diagnostics[name]=diag
  for row in rows:
   ident=(_norm(row.get('league')),_norm(row.get('away')),_norm(row.get('home')));match=next((e for e in events if (_norm(e.get('league')),_norm(e.get('away')),_norm(e.get('home')))==ident),None);evidence={'providerEventId':row.get('providerEventId'),'provider':row.get('source'),'checkedAtUtc':checked}
   if match:match.update({'tag':'LIVE','status':'LIVE','state':'in','liveStateSource':'official-adapter','liveEvidence':evidence});match.setdefault('liveEvidenceOfficial',[]).append(evidence);corroborated+=1
   else:row['liveEvidence']=evidence;row['liveStateSource']='official-adapter';row['liveEvidenceOfficial']=[evidence];events.append(row);added+=1
 payload['events']=events;payload['officialLiveAdapters']={'checkedAtUtc':checked,'diagnostics':diagnostics,'liveAdded':added,'liveCorroborated':corroborated};payload.setdefault('liveSweep',{})['officialAdapters']=diagnostics;FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
