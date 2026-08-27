#!/usr/bin/env python3
"""Generate the ticker's source manifest without putting news calls on the UI thread."""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT=Path('data/sports_news_sources.json')
SOURCES=[
 {'name':'Google Sports Search','type':'discovery','priority':100,'officialOnly':True},
 {'name':'Google News Sports','type':'news','priority':90,'officialOnly':False},
 {'name':'YouTube Official Sports','type':'video','priority':80,'officialOnly':True},
]
TOPICS=['breaking','injury','trade','signing','suspension','postponed','cancelled','playoff','championship','record','final','live','schedule','broadcast']
LEAGUES=['NFL','NCAA FB','NCAA FCS','NBA','WNBA','NCAA BB','NCAA WBB','MLB','NHL','NCAA BASEBALL','NCAA SOFTBALL','NCAA MEN HOCKEY','NCAA WOMEN HOCKEY','NCAA VB','NCAA MEN SOCCER','NCAA WOMEN SOCCER','NCAA MEN LAX','NCAA WOMEN LAX','NCAA WRESTLING','MLS','EPL','UCL','LaLiga','Serie A','Bundesliga','Ligue 1','UFC','BOXING','F1','NASCAR','INDYCAR']

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({'schema':1,'generatedAt':datetime.now(timezone.utc).isoformat(),'ttlMinutes':30,'playbackBlocking':False,'sources':SOURCES,'priorityTopics':TOPICS,'leagues':LEAGUES},indent=2)+'\n',encoding='utf-8')
 print('wrote sports news source manifest')
if __name__=='__main__':main()
