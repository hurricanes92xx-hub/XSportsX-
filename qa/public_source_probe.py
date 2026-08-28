#!/usr/bin/env python3
"""End-to-end probe for every enabled public playlist in the registry."""
import json, os, re, sys, time
from urllib.request import Request, urlopen
REGISTRY=os.path.join(os.path.dirname(__file__),'..','public-sources-registry.json')
TIMEOUT=int(os.getenv('PUBLIC_SOURCE_TIMEOUT','12'))

def fetch(url, headers=None):
    h={'User-Agent':'XSportsX-QA/1.0','Accept':'*/*'}; h.update(headers or {})
    t=time.time()
    with urlopen(Request(url,headers=h),timeout=TIMEOUT) as r: return r.status,r.read(),time.time()-t

def parse(data):
    lines=[x.strip() for x in data.decode('utf-8','replace').splitlines()]; out=[]; meta=None
    for x in lines:
        if x.startswith('#EXTINF:'): meta=x
        elif x and not x.startswith('#') and meta:
            name=meta.split(',',1)[1].strip() if ',' in meta else ''
            m=re.search(r'group-title="([^"]*)"',meta,re.I)
            out.append((name,m.group(1) if m else '',x)); meta=None
    return out

def main():
    with open(REGISTRY,encoding='utf-8') as f: reg=json.load(f)
    sources=[s for s in reg.get('sources',[]) if s.get('enabled') and s.get('public')]
    print(f'PUBLIC_SOURCE_QA registry={reg.get("version")} total={len(sources)}')
    failed=0
    for s in sources:
        try:
            status,data,elapsed=fetch(s['playlist']); entries=parse(data)
            sports=[e for e in entries if any(k in (e[0]+' '+e[1]).lower() for k in ('sport','espn','nfl','nba','nhl','mlb','nascar','racing','soccer','football','hockey','golf','tennis','wwe','ufc'))]
            samples=(sports or entries)[:3]; reachable=0
            for _,_,url in samples:
                try:
                    r,_,_=fetch(url,{'Range':'bytes=0-1023'}); reachable += 1 if 200 <= r < 500 else 0
                except Exception: pass
            print(json.dumps({'id':s['id'],'name':s['name'],'playlist_status':status,'entries':len(entries),'sports_entries':len(sports),'sample_streams':len(samples),'reachable_streams':reachable,'elapsed_sec':round(elapsed,2)},separators=(',',':')))
            if status>=400 or not entries: failed+=1
        except Exception as e:
            failed+=1; print(json.dumps({'id':s['id'],'name':s['name'],'error':str(e)[:240]}))
    print(f'PUBLIC_SOURCE_QA_RESULT failures={failed} total={len(sources)}'); return 1 if failed else 0
if __name__=='__main__': sys.exit(main())
