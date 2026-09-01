#!/usr/bin/env python3
"""Classify unresolved NCAA FB/FCS postseason participants as league-art events."""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; FEED=ROOT/'data'/'schedule_feed.json'
ART={'NCAA FB':'https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png','NCAA FCS':'https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png'}
LEAGUES=set(ART)
def norm(s): return re.sub(r'\s+',' ',re.sub(r'[^A-Z0-9#]+',' ',str(s or '').upper())).strip()
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
 p=json.loads(FEED.read_text(encoding='utf-8'));events=p.get('events') or [];converted=0;placeholders=[]
 for e in events:
  league=str(e.get('league') or '').strip()
  if league not in LEAGUES:continue
  title=str(e.get('title') or '').strip();a=str(e.get('away') or '').strip();h=str(e.get('home') or '').strip();aa,hh=split(title)
  if aa and hh:a,h=aa,hh
  ap,hp=placeholder(a),placeholder(h)
  # Any unresolved participant is artwork, while a known participant keeps its team logo.
  if a and h and (ap or hp):
   e['postseasonPlaceholder']=True;e['ncaaFootballPlaceholder']=True;e['leagueArt']=ART[league]
   if ap:
    e['away']=a;e['awayLogo']=ART[league]
   if hp:
    e['home']=h;e['homeLogo']=ART[league]
   if ap and hp:
    e['eventType']='named_event';e['image']=ART[league];e.pop('awayLogo',None);e.pop('homeLogo',None)
   else:
    e['eventType']='team_game'
   placeholders.append({'league':league,'title':title,'start':e.get('start'),'away':a,'home':h,'awayPlaceholder':ap,'homePlaceholder':hp});converted+=1
 p.setdefault('ncaaFootballPostseasonReport',{})['placeholderEvents']=converted;p['ncaaFootballPostseasonReport']['leagues']=sorted(LEAGUES);p['ncaaFootballPostseasonReport']['policy']='Unresolved FBS/FCS postseason, bowl, conference-title, CFP and FCS-playoff participants use NCAA league art; known participants retain team logos.';p['ncaaFootballPostseasonReport']['events']=placeholders
 FEED.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(p['ncaaFootballPostseasonReport'],indent=2,ensure_ascii=False))
if __name__=='__main__':main()
