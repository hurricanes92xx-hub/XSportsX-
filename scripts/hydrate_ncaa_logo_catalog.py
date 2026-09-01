#!/usr/bin/env python3
"""Hydrate the persistent NCAA logo catalog from ESPN's complete team catalog.

This is a lightweight NCAA-only repair/refresh job. The ESPN site teams endpoint
must be requested with a large limit; the old implementation used page-based
requests that repeatedly returned only the first 50 teams.
"""
from __future__ import annotations
import json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'data'/'team_logo_map.json'
HEADERS={'User-Agent':'XSportsX-LogoCatalog/1.1','Accept':'application/json'}
SOURCES={
 'NCAA FB':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA FCS':'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=1000',
 'NCAA BB':'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000',
 'NCAA WBB':'https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/teams?limit=1000',
}
def get(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read().decode('utf-8','ignore'))
def extract(root):
 rows=[]
 for item in root.get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[]) if root.get('sports') else []:
  t=item.get('team') or {}; logos=t.get('logos') or []
  logo=str(logos[0].get('href') or '').strip() if logos and isinstance(logos[0],dict) else ''
  names={t.get('displayName'),t.get('shortDisplayName'),t.get('name'),t.get('abbreviation'),t.get('slug')}
  for name in names:
   name=str(name or '').strip()
   if name and logo:rows.append((name,logo))
 if not rows:
  for item in root.get('teams',[]) or []:
   t=item.get('team') or item;logos=t.get('logos') or []
   logo=str(logos[0].get('href') or '').strip() if logos and isinstance(logos[0],dict) else ''
   names={t.get('displayName'),t.get('shortDisplayName'),t.get('name'),t.get('abbreviation'),t.get('slug')}
   for name in names:
    name=str(name or '').strip()
    if name and logo:rows.append((name,logo))
 return rows
def main():
 p=json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {'version':3,'teams':{},'sources':{}}
 p.setdefault('teams',{});p.setdefault('sources',{});report={}
 for league,url in SOURCES.items():
  rows=extract(get(url));
  if not rows: raise RuntimeError(f'No teams returned for {league}')
  for name,logo in rows:p['teams'][f'{league}|{name.upper()}']=logo
  p['sources'][league]={'provider':'ESPN official team catalog','teams':len(rows),'url':url,'completeCatalog':True}
  report[league]=len(rows)
 p['generatedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
 CACHE.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print('NCAA logo catalog hydrated:',json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
