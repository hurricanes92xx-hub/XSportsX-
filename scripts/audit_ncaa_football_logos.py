#!/usr/bin/env python3
"""Audit NCAA FB/FCS logo coverage while excluding unresolved postseason participants."""
from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FEED=ROOT/'data'/'schedule_feed.json';OUT=ROOT/'data'/'ncaa_football_logo_audit.json'
LEAGUES={'NCAA FB','NCAA FCS'}
def norm(s):return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9#]+',' ',str(s or '').upper())).strip()
def placeholder(s):
 n=norm(s)
 if not n:return True
 if n in {'TBD','TBA','TO BE DETERMINED','UNKNOWN','WINNER','LOSER','HIGHER SEED','LOWER SEED','CONFERENCE CHAMPION','CONFERENCE RUNNER UP','CONFERENCE RUNNER-UP'}:return True
 if re.search(r'\b(?:CFP|FCS|FBS)?\s*(?:#?\d+\s*)?SEED\b',n):return True
 if re.search(r'\b(?:WINNER|LOSER|CHAMPION|RUNNER UP|RUNNER-UP)\b',n):return True
 if re.search(r'\b(?:CONFERENCE|BOWL|PLAYOFF|CHAMPIONSHIP)\b',n) and re.search(r'\b(?:TBD|TBA|SEED|WINNER|LOSER|CHAMPION|RUNNER)\b',n):return True
 return False
def split(t):
 for p in (r'^(.+?)\s+@\s+(.+)$',r'^(.+?)\s+AT\s+(.+)$',r'^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$'):
  m=re.match(p,str(t or '').strip(),re.I)
  if m:return m.group(1).strip(),m.group(2).strip()
 return '',''
def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];reports={}
 for league in sorted(LEAGUES):
  rows=[];variants=Counter();total=complete=placeholders=placeholder_slots=0
  for e in events:
   if str(e.get('league') or '').strip()!=league:continue
   total+=1;a=str(e.get('away') or '').strip();h=str(e.get('home') or '').strip();aa,hh=split(e.get('title'))
   if aa and hh:a,h=aa,hh
   ap,hp=placeholder(a),placeholder(h)
   if ap or hp:
    placeholders+=1;placeholder_slots+=int(ap)+int(hp)
   # Validate every resolved participant even when its opponent is a postseason placeholder.
   al='' if ap else str(e.get('awayLogo') or '').strip();hl='' if hp else str(e.get('homeLogo') or '').strip()
   if ap and hp:continue
   if a and h and al and hl:complete+=1;continue
   row={'title':str(e.get('title') or ''),'start':e.get('start'),'away':a,'home':h,'awayPlaceholder':ap,'homePlaceholder':hp,'awayLogoPresent':bool(al) if not ap else True,'homeLogoPresent':bool(hl) if not hp else True}
   if not ap and not al:variants[a]+=1
   if not hp and not hl:variants[h]+=1
   # If the only unresolved side is a legitimate placeholder, it is not an actionable logo gap.
   if (ap or hp) and ((ap or al) and (hp or hl)):
    continue
   rows.append(row)
  ma=sum(1 for r in rows if not r['awayLogoPresent'] and r['homeLogoPresent']);mh=sum(1 for r in rows if r['awayLogoPresent'] and not r['homeLogoPresent']);both=sum(1 for r in rows if not r['awayLogoPresent'] and not r['homeLogoPresent'])
  reports[league]={'games_total':total,'placeholder_events':placeholders,'placeholder_logo_slots':placeholder_slots,'complete_resolved_games':complete,'actionable_incomplete_games':len(rows),'missing_away_only':ma,'missing_home_only':mh,'both_missing':both,'missing_logo_slots':sum(variants.values()),'unresolved_variants':[{'exact':k,'count':v,'normalized':norm(k)} for k,v in variants.most_common()],'games':rows}
 status='PASS' if all(v['actionable_incomplete_games']==0 for v in reports.values()) else 'ACTIONABLE_GAPS'
 out={'schema_version':2,'status':status,'leagues':reports,'decision':'Unresolved FBS/FCS postseason, bowl, conference-title, CFP and FCS-playoff participants use NCAA league art. Known participants are still audited for real logo coverage.'}
 OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(out,indent=2,ensure_ascii=False))
 if status!='PASS':raise SystemExit(2)
if __name__=='__main__':main()
