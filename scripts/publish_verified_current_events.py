import json
from datetime import datetime, timezone
from pathlib import Path
from event_identity import event_identity

FEED=Path('data/schedule_feed.json')
NOW=datetime.now(timezone.utc)

def add_or_replace(events, wanted):
    target=wanted['id']; kept=[]
    for e in events:
        if e.get('id')==target: continue
        # Remove the known bad pre-existing Raw timestamp from the Sep 4 snapshot.
        if str(e.get('league'))=='WWE' and str(e.get('title')).strip().lower()=='monday night raw' and str(e.get('start') or e.get('startUtc'))=='2026-09-07T00:00:00Z':
            continue
        kept.append(e)
    kept.append(wanted)
    return kept

def make(league,title,start,source,url,tag='UPCOMING'):
    e={'league':league,'title':title,'start':start,'startUtc':start,'tag':tag,'state':'','source':source,'officialScheduleUrl':url,'officialVerifiedAt':NOW.replace(microsecond=0).isoformat().replace('+00:00','Z')}
    e['id']=event_identity(league,title,start,None,None)
    return e

feed=json.loads(FEED.read_text(encoding='utf-8'))
events=[e for e in feed.get('events',[]) if isinstance(e,dict)]
# WWE official page verified Sep 4: SmackDown tonight, AAA Saturday, SNME Sunday.
wwe='https://www.wwe.com/article/wwe-upcoming-events'
for e in [
    make('WWE','SmackDown','2026-09-05T00:00:00Z','official',wwe),
    make('AAA Wrestling','AAA Lucha Libre','2026-09-06T02:00:00Z','official',wwe),
    make('WWE',"Sunday Night's Main Event",'2026-09-07T00:00:00Z','official',wwe),
    make('WWE','Monday Night Raw','2026-09-08T00:00:00Z','official-recurring',wwe),
]: events=add_or_replace(events,e)
# UFC official event page verified Sep 5 at 3 PM EDT / 19:00 UTC.
ufc='https://www.ufc.com/event/ufc-fight-night-september-05-2026'
e=make('UFC','UFC Fight Night: Hooker vs Parnasse','2026-09-05T19:00:00Z','official',ufc)
e['sport']='MMA';e['broadcast']='Paramount+'
e['venue']='Accor Arena, Paris, France'
events=add_or_replace(events,e)
events.sort(key=lambda x:x.get('start') or x.get('startUtc') or '')
feed['events']=events
counts={}
for e in events: counts[str(e.get('league') or 'Unknown')]=counts.get(str(e.get('league') or 'Unknown'),0)+1
feed['eventCounts']=counts
feed['verifiedCurrentEventRepair']={'updatedAt':NOW.replace(microsecond=0).isoformat().replace('+00:00','Z'),'wwe':['SmackDown','AAA Lucha Libre',"Sunday Night's Main Event",'Monday Night Raw'],'ufc':['UFC Fight Night: Hooker vs Parnasse'],'removedBadRawTimestamp':'2026-09-07T00:00:00Z'}
FEED.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('VERIFIED_CURRENT_EVENTS_PUBLISHED')
