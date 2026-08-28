#!/usr/bin/env python3
"""Probe the exact public source registry used by XSportsX.

This intentionally tests registry -> playlist -> sports-channel extraction ->
representative stream URL reachability. It does not require credentials.
"""
import json, os, re, sys, time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REGISTRY = os.path.join(os.path.dirname(__file__), '..', 'public-sources-registry.json')
TIMEOUT = int(os.getenv('PUBLIC_SOURCE_TIMEOUT', '12'))
MAX_STREAMS = int(os.getenv('PUBLIC_SOURCE_STREAM_SAMPLES', '3'))


def fetch(url):
    req = Request(url, headers={'User-Agent': 'XSportsX-QA/1.0', 'Accept': '*/*'})
    started = time.time()
    with urlopen(req, timeout=TIMEOUT) as r:
        data = r.read()
        return r.status, r.headers.get('content-type', ''), data, time.time() - started


def parse_m3u(data):
    text = data.decode('utf-8', errors='replace')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    entries=[]; meta=None
    for line in lines:
        if line.startswith('#EXTINF:'):
            meta=line
        elif not line.startswith('#') and meta:
            name=meta.split(',',1)[1].strip() if ',' in meta else ''
            group=''
            m=re.search(r'group-title="([^"]*)"', meta, re.I)
            if m: group=m.group(1)
            entries.append({'name':name,'group':group,'url':line})
            meta=None
    return entries


def main():
    with open(REGISTRY, encoding='utf-8') as f: reg=json.load(f)
    sources=[s for s in reg.get('sources',[]) if s.get('enabled') and s.get('public')]
    if not sources:
        print('FAIL: no enabled public sources'); return 1
    failures=0
    print(f'PUBLIC_SOURCE_QA registry_version={reg.get("version")} sources={len(sources)}')
    for s in sources:
        t=time.time()
        try:
            status,ctype,data,elapsed=fetch(s['playlist'])
            entries=parse_m3u(data)
            kind=s.get('kind','')
            sports=[e for e in entries if any(x in (e['group']+' '+e['name']).lower() for x in ('sport','espn','nfl','nba','nhl','mlb','nascar','racing','soccer','football','hockey','golf','tennis','wwe','ufc'))]
            samples=(sports or entries)[:MAX_STREAMS]
            playable=0; stream_errors=[]
            for e in samples:
                try:
                    req=Request(e['url'], headers={'User-Agent':'XSportsX-QA/1.0','Range':'bytes=0-1023'})
                    with urlopen(req, timeout=TIMEOUT) as r:
                        if 200 <= r.status < 500: playable += 1
                except Exception as ex:
                    stream_errors.append(str(ex)[:160])
            print(json.dumps({'id':s['id'],'name':s['name'],'kind':kind,'playlist_status':status,'bytes':len(data),'entries':len(entries),'sports_entries':len(sports),'stream_samples':len(samples),'stream_reachable':playable,'elapsed_sec':round(elapsed,2),'stream_errors':stream_errors}, separators=(',',':')))
            if status < 200 or status >= 400 or not entries:
                failures += 1
        except Exception as ex:
            failures += 1
            print(json.dumps({'id':s['id'],'name':s['name'],'error':str(ex)[:240]}))
    print(f'PUBLIC_SOURCE_QA_RESULT failures={failures} total={len(sources)}')
    return 1 if failures else 0

if __name__ == '__main__': sys.exit(main())
