#!/usr/bin/env python3
"""Audit NCAA FB/FCS logos while excluding legitimate unresolved postseason placeholders."""
from __future__ import annotations
import json, re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'; OUT=ROOT/'data'/'ncaa_football_logo_audit.json'
LEAGUES={'NCAA FB','NCAA FCS'}
def norm(s): return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9#]+',' ',str(s or '').upper())).strip()
def placeholder(s):
 n=norm(s)
 if not n:return True
 if n in {'TBD','TBA','TO BE DETERMINED','UNKNOWN','WINNER','LOSER','HIGHER SEED','LOWER SEED'}:return True
 if re.search(r'\b(?:SEED)\b',n):return True
 if re.search(r'\b(?:WINNER|LOSER)\b',n):return True
 if re.search(r'\b(?:CONFERENCE|BOWL|PLAYOFF|CHAMPIONSHIP)\b',n) and re.search(r'\b(?:TBD|WINNER|SEED|CHAMPION|RUNNER UP|RUNNER-UP)\b',n):return True
 return False
def split(t):
 for p in (r'^(.+?)\s+@\s+(.+)$',r'^(.+?)\s+AT\s+(.+)$',r'^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$'):
  m=re.match(p,str(t or '').strip(),re.I)
  if m:return m.group(1).strip(),m.group(2).strip()
 return '',''
def main():
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or []; reports={}
 for league in LEAGUES:
  rows=[]; variants=Counter(); total=complete=placeholders=0
  for e in events:
   if str(e.get('league') or '').strip()!=league:continue
   total+=1; a=str(e.get('away') or '').strip();h=str(e.get('home') or '').strip(); aa,hh=split(e.get('title'))
   if aa and hh:a,h=aa,hh
   isph=bool(e.get('ncaaFootballPlaceholder') or e.get('postseasonPlaceholder') or (a and h and placeholder(a) and placeholder(h)))
   if isph:placeholders+=1;continue
   al=str(e.get('awayLogo') or '').strip();hl=str(e.get('homeLogo') or '').strip()
   if al and hl:complete+=1;continue
   row={'title':str(e.get('title') or ''),'start':e.get('start'),'away':a,'home':h,'awayLogoPresent':bool(al),'homeLogoPresent':bool(hl)}
   rows.append(row)
   if not al:variants[a]+=1
   if not hl:variants[h]+=1
  missing_away=sum(1 for r in rows if not r['awayLogoPresent'] and r['homeLogoPresent']);missing_home=sum(1 for r in rows if r['awayLogoPresent'] and not r['homeLogoPresent']);both=sum(1 for r in rows if not r['awayLogoPresent'] and not r['homeLogoPresent'])
  reports[league]={'games_total':total,'placeholder_events':placeholders,'complete_team_games':complete,'actionable_incomplete_games':len(rows),'missing_away_only':missing_away,'missing_home_only':missing_home,'both_missing':both,'missing_logo_slots':sum(variants.values()),'unresolved_variants':[{'exact':k,'count':v} for k,v in variants.most_common()],'games':rows}
 out={'schema_version':1,'leagues':reports,'decision':'NCAA FB/FCS postseason, bowl, conference-championship, CFP/FCS-playoff placeholders are valid when both participants are unresolved; real team-vs-team games remain actionable if logos are missing.'}
 OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(out,indent=2,ensure_ascii=False))
 if any(v['actionable_incomplete_games'] for v in reports.values()):raise SystemExit(2)
if __name__=='__main__':main()
