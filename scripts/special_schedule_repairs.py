#!/usr/bin/env python3
"""Targeted repairs for leagues whose official pages are JS-heavy or have drifted.

Sources are public/official where possible and are only used to add real events.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

FEED = Path('data/schedule_feed.json')
HEADERS = {'User-Agent':'XSportsX-Schedule/5.4','Accept':'application/json,text/html,*/*'}


def fetch(url, accept=None):
    h = dict(HEADERS)
    if accept: h['Accept'] = accept
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_json(url):
    return json.loads(fetch(url, 'application/json').decode('utf-8','ignore'))


def add_row(events, league, title, start, source, icon='🏆'):
    if not start: return False
    try:
        dt=datetime.fromisoformat(start.replace('Z','+00:00')).astimezone(timezone.utc)
        start=dt.isoformat().replace('+00:00','Z')
    except ValueError:
        return False
    key=(league,title,start)
    if key in {(e.get('league'),e.get('title'),e.get('start')) for e in events}:
        return False
    events.append({'league':league,'title':title,'start':start,'tag':'UPCOMING','icon':icon,'source':source})
    return True


def repair_espn_lacrosse(events, report, failures):
    now=datetime.now(timezone.utc).date(); end=now+timedelta(days=45)
    for league_name, slug in [('PLL','pll'),('NLL','nll')]:
        added=0; healthy=False
        for host in ('site.web.api.espn.com','site.api.espn.com'):
            url=f'https://{host}/apis/site/v2/sports/lacrosse/{slug}/scoreboard?dates={now:%Y%m%d}-{end:%Y%m%d}&limit=1000'
            try:
                root=fetch_json(url); healthy=True
                for ev in root.get('events') or []:
                    comp=(ev.get('competitions') or [{}])[0]
                    teams=comp.get('competitors') or []
                    home=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='home'),'')
                    away=next((x.get('team',{}).get('shortDisplayName') or x.get('team',{}).get('displayName') for x in teams if x.get('homeAway')=='away'),'')
                    title=f'{away} @ {home}' if home and away else ev.get('name') or league_name
                    if add_row(events,league_name,title,ev.get('date'),'espn', '🥍'): added+=1
                break
            except Exception as exc:
                print(f'WARNING ESPN {league_name}: {exc}')
        report[league_name]={'source':'ESPN lacrosse scoreboard','added':added,'healthy':healthy}
        if healthy:
            failures[:] = [x for x in failures if x != league_name]
            print(f'REPAIRED {league_name}: source healthy, added={added}')
        else:
            print(f'NO REPAIR {league_name}: ESPN unavailable')


def repair_motogp(events, report, failures):
    url='https://api.motogp.pulselive.com/motogp/v1/events?seasonYear=2026'
    try:
        root=fetch_json(url)
        added=0
        for ev in root if isinstance(root,list) else []:
            cats=ev.get('categories') or []
            if not any(str(c.get('name','')).lower().startswith('motogp') or c.get('acronym')=='MGP' for c in cats):
                continue
            start=ev.get('date_start')
            if add_row(events,'MotoGP',ev.get('name') or ev.get('shortname') or 'MotoGP',start,'motogp.pulselive.com','🏍️'): added+=1
        report['MotoGP']={'source':'MotoGP public API','parsed':len(root) if isinstance(root,list) else 0,'added':added}
        failures[:] = [x for x in failures if x != 'MotoGP']
        print(f'REPAIRED MotoGP: API healthy, parsed={len(root) if isinstance(root,list) else 0}, added={added}')
    except Exception as exc:
        print(f'NO REPAIR MotoGP: {exc}')


class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data):
        t=' '.join(data.split())
        if t:self.parts.append(t)
    def text(self): return ' '.join(self.parts)


def repair_mxgp(events, report, failures):
    # MXGP's own calendar intermittently fails TLS on hosted runners. Honda Racing
    # republishes the MXGP calendar in a stable HTML page and is a team/manufacturer
    # source, so use it as the fallback calendar authority.
    url='https://honda.racing/mxgp/calendar'
    try:
        text=Text(); text.feed(fetch(url,'text/html,*/*').decode('utf-8','ignore')); s=text.text()
        # Match the visible round/date/title blocks. Month names are unambiguous.
        rx=re.compile(r'Round\s+(\d+)\s+(.*?)\s+(\d{1,2})\s*-\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+2026',re.I)
        matches=list(rx.finditer(s)); added=0
        for m in matches:
            title=' '.join(m.group(2).split())
            month=m.group(5); day=int(m.group(3))
            try: start=datetime.strptime(f'2026 {month} {day} 12:00','%Y %B %d %H:%M').replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
            except ValueError: continue
            if add_row(events,'MXGP',title,start,'honda.racing','🏍️'): added+=1
        if not matches: raise RuntimeError('calendar HTML did not expose round/date blocks')
        report['MXGP']={'source':'Honda Racing MXGP calendar','parsed':len(matches),'added':added}
        failures[:] = [x for x in failures if x != 'MXGP']
        print(f'REPAIRED MXGP: Honda Racing calendar parsed={len(matches)}, added={added}')
    except Exception as exc:
        print(f'NO REPAIR MXGP: {exc}')


def repair_monster_jam(events, report, failures):
    url='https://www.monsterjam.com/en-us/tickets/'
    try:
        s=fetch(url,'text/html,*/*').decode('utf-8','ignore')
        # The official page embeds a JSON-like API payload with Engagement objects.
        pat=re.compile(r'\"City\"\s*:\s*\"([^\"]+)\".*?\"VenueName\"\s*:\s*\"([^\"]+)\".*?\"StartDate\"\s*:\s*\"(2026-\d{2}-\d{2}T[^\"]+)\"',re.S)
        matches=list(pat.finditer(s)); added=0
        for m in matches:
            city, venue, start=m.groups()
            title=f'Monster Jam — {city} — {venue}'
            if add_row(events,'MONSTER JAM',title,start,'monsterjam.com','🏁'): added+=1
        if not matches: raise RuntimeError('official Monster Jam API payload not found')
        report['MONSTER JAM']={'source':'MonsterJam official embedded API','parsed':len(matches),'added':added}
        failures[:] = [x for x in failures if x != 'MONSTER JAM']
        print(f'REPAIRED MONSTER JAM: official API parsed={len(matches)}, added={added}')
    except Exception as exc:
        print(f'NO REPAIR MONSTER JAM: {exc}')


def main():
    p=json.loads(FEED.read_text(encoding='utf-8')); events=p.get('events') or []
    failures=list(p.get('officialSourceFailures') or []); report=p.setdefault('providerRepairReport',{})
    repair_espn_lacrosse(events,report,failures)
    repair_motogp(events,report,failures)
    repair_mxgp(events,report,failures)
    repair_monster_jam(events,report,failures)
    p['events']=events; p['officialSourceFailures']=failures
    p['eventCounts']={k:sum(1 for e in events if e.get('league')==k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    p['generatedAt']=datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'special repairs complete: {len(events)} events across {len(p["eventCounts"])} leagues')

if __name__=='__main__': main()
