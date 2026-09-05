#!/usr/bin/env python3
"""Dedicated official live adapters for FIVB and NASCAR."""
from __future__ import annotations
import json, urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; FEED=ROOT/'data'/'schedule_feed.json'; UA='XSportsX-OfficialLiveAdapters/1.7'; FIVB_URL='https://www.fivb.org/Vis2009/XmlRequest.asmx'; FIVB_LIVE_URL='https://www.fivb.org/Vis2009/GetVolleyLive.asmx'
def _get(url,timeout=10,headers=None,raw=False):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/plain,*/*',**(headers or {})})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  data=r.read()
  return data if raw else json.loads(data.decode('utf-8','ignore'))
def _post_xml(xml,timeout=12,accept='application/xml,text/xml,*/*'):
 req=urllib.request.Request(FIVB_URL,data=xml.encode('utf-8'),headers={'User-Agent':UA,'Accept':accept,'Content-Type':'text/xml; charset=utf-8'},method='POST')
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()
def _fivb_get_xml(url,timeout=12):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/xml,text/xml,*/*'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:return r.read(),r.status,''
 except urllib.error.HTTPError as exc:
  body=exc.read().decode('utf-8','replace')[:1200]
  return body.encode(),exc.code,body
def _iso(v):
 if not v:return ''
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
 except:return ''
def _norm(v):return ''.join(c.lower() for c in str(v or '') if c.isalnum())
LIVE_STATUS_NUM={5,8,11,14,17,20,23};LIVE_STATUS_NAMES={f'inset{i}' for i in range(1,8)}
def _is_live(v):
 s=_norm(v)
 try:return int(str(v).strip()) in LIVE_STATUS_NUM
 except:return s in LIVE_STATUS_NAMES
def _field(el,*names):
 wanted={n.lower() for n in names}
 for k,v in el.attrib.items():
  if k.lower() in wanted and str(v).strip():return str(v).strip()
 for child in el:
  if child.tag.split('}')[-1].lower() in wanted and child.text and child.text.strip():return child.text.strip()
 return ''
def _desc_field(el,*names):
 value=_field(el,*names)
 if value:return value
 wanted={n.lower() for n in names}
 for node in el.iter():
  if node is el:continue
  if node.tag.split('}')[-1].lower() in wanted:
   if node.text and node.text.strip():return node.text.strip()
   for k,v in node.attrib.items():
    if k.lower() in wanted and str(v).strip():return str(v).strip()
 return ''
def _fivb_records(root):
 return [el for el in root.iter() if el.tag.split('}')[-1].lower() in {'volleyballmatch','volleymatch','match'} and _desc_field(el,'No','NoMatch','NoVolleyMatch').isdigit()]
def _parse_fivb_live(raw):
 try:
  root=ET.fromstring(raw)
  tags={n.tag.split('}')[-1].lower() for n in root.iter()}
  if 'volleylive' in tags:return True,'volleylive',root
  if 'nochanges' in tags or 'notmodified' in tags:return True,'nochanges',root
  errors=[]
  for n in root.iter():
   t=n.tag.split('}')[-1].lower()
   if 'error' in t:
    errors.append((_field(n,'Code','code'),_field(n,'Text','text','Message','message')))
  return False,'response:'+(';'.join(':'.join(x) for x in errors) or ','.join(sorted(tags)) or 'empty'),root
 except Exception as exc:return False,f'parse:{type(exc).__name__}',None
def _fivb_live_request(no):
 no=int(no); attempts=[]
 # FIVB documents GetVolleyLive.asmx as the dedicated HTTP endpoint. Try the
 # documented parameter name first, then the legacy No name used by VIS XML.
 for endpoint in (FIVB_LIVE_URL,FIVB_URL):
  for name in ('NoVolleyMatch','No'):
   params=urllib.parse.urlencode({name:no,'Options':128,'Version':0})
   attempts.append(('GET',endpoint+'?'+params))
  # The generic XmlRequest also accepts a request in the HTTP payload.
  attempts.append(('POST',endpoint if endpoint==FIVB_URL else endpoint, f'<Request Type="GetVolleyLive" No="{no}" Options="128" Version="0" />'))
 reasons=[]
 for item in attempts:
  try:
   if item[0]=='GET':raw,status,body=_fivb_get_xml(item[1])
   else:
    raw=_post_xml(item[2]);status=200;body=''
   ok,why,_=_parse_fivb_live(raw)
   if ok:return True,f'{item[0]}:{item[1]}:{why}'
   reasons.append(f'{item[0]}:{item[1]}:{why}')
  except urllib.error.HTTPError as exc:
   body=exc.read().decode('utf-8','replace')[:1200]
   reasons.append(f'{item[0]}:{item[1]}:http:{exc.code}:{body}')
  except Exception as exc:reasons.append(f'{item[0]}:{item[1]}:{type(exc).__name__}:{str(exc)[:200]}')
 return False,' || '.join(reasons)
def _fivb():
 result=[];d={'status':'ok','listRecords':0,'candidates':0,'liveVerified':0,'liveRejected':0,'errors':[],'verification':{}}
 request='<Request Type="GetVolleyMatchList" Fields="No DateTimeUtc BeginDateTimeUtc TeamNameA TeamNameB Status Gender TournamentName HasLiveData"><Filter ForLiveScore="true" /></Request>'
 try:root=ET.fromstring(_post_xml(request))
 except Exception as exc:d['status']='unavailable';d['errors'].append(f'list:{type(exc).__name__}:{str(exc)[:300]}');return result,d
 records=_fivb_records(root);d['listRecords']=len(records)
 for el in records:
  no=_desc_field(el,'No','NoMatch','NoVolleyMatch');status=_desc_field(el,'Status','StatusName','MatchStatus')
  if not _is_live(status):continue
  d['candidates']+=1;home=_desc_field(el,'TeamNameA','TeamAName','NameA','TeamA');away=_desc_field(el,'TeamNameB','TeamBName','NameB','TeamB');start=_iso(_desc_field(el,'DateTimeUtc','BeginDateTimeUtc','DateUtc'));gender=_norm(_desc_field(el,'Gender','TournamentGender'));tournament=_desc_field(el,'TournamentName','Name');league='FIVB Women' if gender in {'w','women','female','f'} or 'women' in _norm(tournament) or 'feminin' in _norm(tournament) else 'FIVB Men'
  ok,why=_fivb_live_request(no);d['verification'][str(no)]=why
  if not ok:d['liveRejected']+=1;continue
  result.append({'league':league,'title':f'{away} @ {home}' if away and home else f'FIVB Match {no}','start':start,'startUtc':start,'tag':'LIVE','status':'LIVE','state':'in','home':home,'away':away,'source':'fivb-vis-official','providerEventId':f'fivb:{no}','liveEvidenceSource':'fivb-vis'});d['liveVerified']+=1
 return result,d
def _nascar():
 result=[];d={'status':'ok','liveFeed':False,'scheduleRecords':0,'liveVerified':0,'errors':[]}
 for version in ('1','2'):
  try:
   root=_get(f'https://feed.nascar.com/api/LiveFeed?v={version}',headers={'Referer':'https://www.nascar.com/','Origin':'https://www.nascar.com'})
   d['liveFeed']=True
   for x in root if isinstance(root,list) else [root]:
    if not isinstance(x,dict) or str(x.get('series_id') or x.get('seriesId'))!='3':continue
    rid=x.get('race_id') or x.get('raceId') or x.get('run_id');nm=x.get('run_name') or x.get('event_name') or 'NASCAR Craftsman Truck Series';start=_iso(x.get('time_of_day_os') or x.get('start_time_utc') or x.get('start_time'));result.append({'league':'NASCAR Truck','title':nm,'start':start,'startUtc':start,'tag':'LIVE','status':'LIVE','state':'in','source':'nascar-livefeed-official','providerEventId':f'nascar:live:{rid}','liveEvidenceSource':'nascar-livefeed'});d['liveVerified']+=1
   if result:return result,d
   break
  except Exception as exc:d['errors'].append(f'livefeed:{type(exc).__name__}')
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
