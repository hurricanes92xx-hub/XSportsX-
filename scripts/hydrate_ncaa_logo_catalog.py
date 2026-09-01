#!/usr/bin/env python3
"""Hydrate the persistent NCAA FBS/FCS logo catalog from ESPN's official team catalog."""
from __future__ import annotations
import json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CACHE=ROOT/'data'/'team_logo_map.json'
HEADERS={'User-Agent':'Mozilla/5.0 XSportsX-LogoCatalog/1.0','Accept':'application/json'}
SOURCES={
 'NCAA FB':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA FCS':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000&groups=81',
}
def get(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))
def main():
 p=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':3,'teams':{},'sources':{}}
 p.setdefault('teams',{}); p.setdefault('sources',{}); report={}
 for league,url in SOURCES.items():
  root=get(url); rows=[]
  for item in root.get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[]) if root.get('sports') else []:
   t=item.get('team') or {}
   name=str(t.get('displayName') or t.get('shortDisplayName') or t.get('name') or '').strip(); logo=''
   logos=t.get('logos') or []
   if logos and isinstance(logos[0],dict): logo=str(logos[0].get('href') or '').strip()
   if name and logo: rows.append((name,logo))
  # Some ESPN responses expose teams directly.
  if not rows:
   for item in root.get('teams',[]) or []:
    t=item.get('team') or item; name=str(t.get('displayName') or t.get('shortDisplayName') or t.get('name') or '').strip(); logos=t.get('logos') or []
    logo=str(logos[0].get('href') or '').strip() if logos and isinstance(logos[0],dict) else ''
    if name and logo: rows.append((name,logo))
  for name,logo in rows:p['teams'][f'{league}|{name.upper()}']=logo
  p['sources'][league]={'provider':'ESPN official team catalog','teams':len(rows),'url':url}
  report[league]=len(rows)
 p['generatedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 CACHE.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('NCAA logo catalog hydrated:',json.dumps(report,sort_keys=True))
 assert all(report.get(k,0)>0 for k in SOURCES), report
if __name__=='__main__':main()
