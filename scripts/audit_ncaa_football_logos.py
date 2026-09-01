#!/usr/bin/env python3
"""Audit and repair NCAA FB/FCS logo coverage from the persistent cache."""
from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FEED=ROOT/'data'/'schedule_feed.json';CACHE=ROOT/'data'/'team_logo_map.json';OUT=ROOT/'data'/'ncaa_football_logo_audit.json'
LEAGUES={'NCAA FB','NCAA FCS'}
ALIASES={'MIAMI OH REDHAWKS':['MIAMI REDHAWKS','MIAMI OH'],'TEXAS A M AGGIES':['TEXAS A M','TEXAS AM'],'TEXAS A M':['TEXAS A M','TEXAS AM'],'LOUISIANA RAGIN CAJUNS':['LOUISIANA','LOUISIANA LAFAYETTE'],'GARDNER WEBB':['GARDNER WEBB','GARDNER WEBB RUNNIN BULLDOGS'],'GARDNER WEBB RUNNIN BULLDOGS':['GARDNER WEBB'],'AR PINE BLUFF':['ARKANSAS PINE BLUFF','ARKANSAS PINE BLUFF GOLDEN LIONS'],'ARKANSAS PINE BLUFF GOLDEN LIONS':['ARKANSAS PINE BLUFF'],'NC A T':['NORTH CAROLINA A T','NORTH CAROLINA A T AGGIES'],'NORTH CAROLINA A T AGGIES':['NORTH CAROLINA A T','NC A T'],'UT RIO GRANDE':['UT RIO GRANDE VALLEY','UT RIO GRANDE VALLEY VAQUEROS'],'UT RIO GRANDE VALLEY VAQUEROS':['UT RIO GRANDE VALLEY','UT RIO GRANDE'],'N WESTERN ST':['NORTHWESTERN STATE','NORTHWESTERN STATE DEMONS'],'EAST TEXAS A M':['EAST TEXAS A M','EAST TEXAS A M LIONS'],'EAST TEXAS A M LIONS':['EAST TEXAS A M'],'WILLIAM MARY':['WILLIAM MARY','WILLIAM MARY TRIBE'],'WILLIAM MARY TRIBE':['WILLIAM MARY'],'BETHUNE COOKMAN WILDCATS':['BETHUNE COOKMAN','BETHUNE COOKMAN WILDCATS'],'PRAIRIE VIEW A M PANTHERS':['PRAIRIE VIEW A M','PRAIRIE VIEW A M PANTHERS'],'ALABAMA A M BULLDOGS':['ALABAMA A M','ALABAMA A M BULLDOGS'],'ST THOMAS TOMMIES':['ST THOMAS','ST THOMAS TOMMIES'],'STEPHEN F AUSTIN LUMBERJACKS':['STEPHEN F AUSTIN','STEPHEN F AUSTIN LUMBERJACKS'],'CHICAGO STATE COUGARS':['CHICAGO STATE','CHICAGO STATE COUGARS'],'VIRGINIA LYNCHBURG DRAGONS':['VIRGINIA LYNCHBURG','VIRGINIA LYNCHBURG DRAGONS'],'KENTUCKY CHRISTIAN KNIGHTS':['KENTUCKY CHRISTIAN','KENTUCKY CHRISTIAN KNIGHTS'],'CENTRAL STATE OH MARAUDERS':['CENTRAL STATE OH','CENTRAL STATE OH MARAUDERS'],'ARKANSAS BAPTIST BUFFALOES':['ARKANSAS BAPTIST','ARKANSAS BAPTIST BUFFALOES'],'WEBBER INTERNATIONAL WARRIORS':['WEBBER INTERNATIONAL','WEBBER INTERNATIONAL WARRIORS'],'LANE DRAGONS':['LANE','LANE DRAGONS'],'MILES COLLEGE GOLDEN BEARS':['MILES COLLEGE','MILES COLLEGE GOLDEN BEARS'],'TEXAS WESLEYAN RAMS':['TEXAS WESLEYAN','TEXAS WESLEYAN RAMS'],'THOMAS MORE COLLEGE SAINTS':['THOMAS MORE','THOMAS MORE COLLEGE','THOMAS MORE COLLEGE SAINTS'],'DICKINSON PA RED DEVILS':['DICKINSON PA','DICKINSON PA RED DEVILS'],'LINCOLN PA LIONS':['LINCOLN PA','LINCOLN PA LIONS'],'POINT UNIVERSITY SKYHAWKS':['POINT UNIVERSITY','POINT UNIVERSITY SKYHAWKS'],'RIO GRANDE RED STORM':['RIO GRANDE','RIO GRANDE RED STORM'],'MOREHOUSE COLLEGE MAROON TIGERS':['MOREHOUSE COLLEGE','MOREHOUSE COLLEGE MAROON TIGERS'],'UFTL EAGLES':['UFTL','UFTL EAGLES']}
def norm(s):return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9]+',' ',str(s or '').upper())).strip()
def placeholder(s):
    n=norm(s)
    if not n or n in {'TBD','TBA','TO BE DETERMINED','UNKNOWN','WINNER','LOSER','HIGHER SEED','LOWER SEED'}:return True
    return bool(re.search(r'\b(?:SEED|WINNER|LOSER|CHAMPION|RUNNER UP|RUNNER-UP)\b',n))
def split(t):
    for p in (r'^(.+?)\s+@\s+(.+)$',r'^(.+?)\s+AT\s+(.+)$',r'^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$'):
        m=re.match(p,str(t or '').strip(),re.I)
        if m:return m.group(1).strip(),m.group(2).strip()
    return '',''
def strip_mascot(s):
    toks=norm(s).split();masc={'BULLDOGS','BULLDOG','WILDCATS','EAGLES','LIONS','TIGERS','PANTHERS','HAWKS','TOMMIES','TRIBE','REDHAWKS','BEARS','KNIGHTS','DRAGONS','WARRIORS','RAMS','SAINTS','BUFFALOES','DEMONS','COUGARS','MARAUDERS','VAQUEROS','LUMBERJACKS','SKYHAWKS'}
    while toks and toks[-1] in masc:toks.pop()
    return ' '.join(toks)
def resolve(cache,league,team):
    teams=cache.get('teams') or {};n=norm(team);v=teams.get(f'{league}|{n}')
    if isinstance(v,str) and v:return v
    for candidate in ALIASES.get(n,[]):
        v=teams.get(f'{league}|{norm(candidate)}')
        if isinstance(v,str) and v:return v
    core=strip_mascot(n)
    if not core:return ''
    matches=set();prefix=f'{league}|'
    for key,logo in teams.items():
        if not key.startswith(prefix) or not isinstance(logo,str) or not logo:continue
        ccore=strip_mascot(key[len(prefix):])
        if ccore==core or ccore.startswith(core+' ') or core.startswith(ccore+' '):matches.add(logo)
    return next(iter(matches)) if len(matches)==1 else ''
def main():
    payload=json.loads(FEED.read_text(encoding='utf-8'));events=payload.get('events') or []
    try:cache=json.loads(CACHE.read_text(encoding='utf-8'))
    except Exception:cache={'teams':{}}
    repaired=0;reports={}
    for league in sorted(LEAGUES):
        rows=[];variants=Counter();total=complete=placeholders=placeholder_slots=0
        for e in events:
            if str(e.get('league') or '').strip()!=league:continue
            total+=1;a=str(e.get('away') or '').strip();h=str(e.get('home') or '').strip();aa,hh=split(e.get('title'))
            if aa and hh:a,h=aa,hh
            ap,hp=placeholder(a),placeholder(h)
            if ap or hp:placeholders+=1;placeholder_slots+=int(ap)+int(hp)
            if not ap and not e.get('awayLogo'):
                logo=resolve(cache,league,a)
                if logo:e['awayLogo']=logo;repaired+=1
            if not hp and not e.get('homeLogo'):
                logo=resolve(cache,league,h)
                if logo:e['homeLogo']=logo;repaired+=1
            al='' if ap else str(e.get('awayLogo') or '').strip();hl='' if hp else str(e.get('homeLogo') or '').strip()
            if ap and hp:continue
            if a and h and al and hl:complete+=1;continue
            row={'title':str(e.get('title') or ''),'start':e.get('start'),'away':a,'home':h,'awayPlaceholder':ap,'homePlaceholder':hp,'awayLogoPresent':bool(al) if not ap else True,'homeLogoPresent':bool(hl) if not hp else True}
            if not ap and not al:variants[a]+=1
            if not hp and not hl:variants[h]+=1
            if (ap or hp) and ((ap or al) and (hp or hl)):continue
            rows.append(row)
        ma=sum(1 for r in rows if not r['awayLogoPresent'] and r['homeLogoPresent']);mh=sum(1 for r in rows if r['awayLogoPresent'] and not r['homeLogoPresent']);both=sum(1 for r in rows if not r['awayLogoPresent'] and not r['homeLogoPresent'])
        reports[league]={'games_total':total,'placeholder_events':placeholders,'placeholder_logo_slots':placeholder_slots,'complete_resolved_games':complete,'actionable_incomplete_games':len(rows),'missing_away_only':ma,'missing_home_only':mh,'both_missing':both,'missing_logo_slots':sum(variants.values()),'unresolved_variants':[{'exact':k,'count':v,'normalized':norm(k)} for k,v in variants.most_common()],'games':rows}
    status='PASS' if all(v['actionable_incomplete_games']==0 for v in reports.values()) else 'ACTIONABLE_GAPS'
    payload['events']=events;payload.setdefault('repairReport',{})['ncaaLogoAliasesApplied']=repaired
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    out={'schema_version':3,'status':status,'repaired_logo_slots':repaired,'leagues':reports,'decision':'Unresolved FBS/FCS postseason, bowl, conference-title, CFP and FCS-playoff participants use NCAA league art. Known participants are resolved from the persistent NCAA catalog using deterministic aliases; no external logo discovery occurs during refresh.'}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(out,indent=2,ensure_ascii=False))
    if status!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
