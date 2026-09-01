#!/usr/bin/env python3
"""Emit a compact machine-readable audit for selected schedule leagues."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'data' / 'schedule_feed.json'
POLICY = ROOT / 'data' / 'schedule_season_policy.json'
OUT = ROOT / 'data' / 'league_schedule_audit.json'
LEAGUES = ['NBA', 'NLL']
LOOKAHEAD_DAYS = 370

def parse(v):
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None

def in_season(dt, window):
    if not window or len(window) != 2: return True
    md=(dt.month,dt.day); a=tuple(map(int,window[0])); b=tuple(map(int,window[1]))
    return a <= md <= b if a <= b else md >= a or md <= b

p=json.loads(FEED.read_text(encoding='utf-8'))
policy=json.loads(POLICY.read_text(encoding='utf-8')) if POLICY.exists() else {}
reference=parse(p.get('generatedAt')) or datetime.now(timezone.utc)
horizon=reference+timedelta(days=LOOKAHEAD_DAYS)
events=p.get('events') or []
report=p.get('phase2RepairReport') or {}
rows=[]
for league in LEAGUES:
    mine=[]
    for e in events:
        if e.get('league') != league: continue
        dt=parse(e.get('start'))
        if dt: mine.append((dt,e))
    dates=[x[0] for x in mine]
    current=[dt for dt,_ in mine if reference <= dt <= horizon and in_season(dt,(policy.get('leagueWindows') or {}).get(league))]
    stale=[dt for dt,_ in mine if dt < reference or dt > horizon or not in_season(dt,(policy.get('leagueWindows') or {}).get(league))]
    repair=report.get(league) or {}
    rows.append({
        'league': league,
        'event_count': len(mine),
        'min_date': min(dates).isoformat().replace('+00:00','Z') if dates else None,
        'max_date': max(dates).isoformat().replace('+00:00','Z') if dates else None,
        'current_future_count': len(current),
        'stale_or_outside_count': len(stale),
        'season_window': (policy.get('leagueWindows') or {}).get(league),
        'reference': reference.isoformat().replace('+00:00','Z'),
        'horizon': horizon.isoformat().replace('+00:00','Z'),
        'source': repair.get('source'),
        'repair_result': repair,
        'official_source_failure': league in (p.get('officialSourceFailures') or []),
        'provider_failure': league in (p.get('failedSources') or []),
    })

out={
    'schema_version': 1,
    'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    'feed_generated_at': p.get('generatedAt'),
    'leagues': rows,
}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2,ensure_ascii=False))
