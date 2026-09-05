#!/usr/bin/env python3
"""Conservative learning loop for the XSportsX Sports Knowledge Brain.

Only repeated, independently supported observations become lessons. Learned
lessons guide future reasoning but never directly mutate canonical events.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'sports_knowledge'/'learned_lessons.json'
MIN_CONF=.85
MIN_EVIDENCE=2


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def key(*parts): return hashlib.sha256('|'.join(' '.join(str(x or '').lower().split()) for x in parts).encode()).hexdigest()[:20]
def load():
    try:
        d=json.loads(OUT.read_text(encoding='utf-8'))
        if isinstance(d,dict): return d
    except Exception: pass
    return {'schema':1,'policy':{'minimumConfidence':MIN_CONF,'minimumIndependentEvidence':MIN_EVIDENCE,'requireRepeatedObservation':3,'canonicalTruthNeverComesFromLessons':True},'lessons':{}}
def save(d):
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def learn(feed):
    d=load(); lessons=d.setdefault('lessons',{}); observations=feed.get('events') or []
    for e in observations:
        if not isinstance(e,dict): continue
        league=str(e.get('league') or '').strip(); title=str(e.get('title') or '').strip()
        if not league or not title: continue
        source=str(e.get('source') or e.get('sourceProvider') or e.get('provider') or '').lower()
        official=('official' in source) or source in {'ufc','wwe','nfl','mlb','nba','nhl'}
        if not official: continue
        # Stable session vocabulary becomes reusable terminology only after repetition.
        low=title.lower()
        session=next((x for x in ('early prelims','prelims','main card','qualifying','practice','race','monday night raw','smackdown','sunday night’s main event') if x in low),None)
        if not session: continue
        k=key(league,session); item=lessons.setdefault(k,{'id':k,'league':league,'pattern':session,'observations':0,'independentSources':[],'confidence':0.0})
        item['observations']=int(item.get('observations',0))+1
        if source and source not in item['independentSources']: item['independentSources'].append(source)
        item['lastSeen']=now()
        item['confidence']=min(.99,.70+.05*min(4,item['observations'])+.05*min(2,len(item['independentSources'])))
        if item['observations']>=3 and len(item['independentSources'])>=MIN_EVIDENCE and item['confidence']>=MIN_CONF:
            item['status']='validated';item['validatedAt']=item.get('validatedAt') or now()
    d['updatedAt']=now();d['stats']={'lessons':len(lessons),'validated':sum(1 for x in lessons.values() if x.get('status')=='validated')}
    save(d);return d['stats']

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('feed');a=p.parse_args()
    print(json.dumps(learn(json.loads(Path(a.feed).read_text(encoding='utf-8'))),indent=2))
