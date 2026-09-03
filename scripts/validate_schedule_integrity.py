#!/usr/bin/env python3
"""Fail the refresh when canonical output contains structural/data-integrity defects."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from event_identity import canonical_event_key, event_identity, normalize_league

FEED=Path("data/schedule_feed.json")
REQUIRED=("id","sport","league","title","startUtc")


def parse_time(value):
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)


def main():
    data=json.loads(FEED.read_text(encoding="utf-8"))
    events=data.get("events")
    if not isinstance(events,list) or not events:
        raise SystemExit("ERROR: canonical schedule is empty")
    ids=set(); keys=defaultdict(list); bad=[]; bad_ids=[]
    for i,e in enumerate(events):
        if not isinstance(e,dict): bad.append(f"event {i} is not an object"); continue
        missing=[k for k in REQUIRED if not e.get(k)]
        if missing: bad.append(f"event {i} missing {missing}"); continue
        try: parse_time(e["startUtc"])
        except Exception: bad.append(f"event {i} has invalid startUtc={e.get('startUtc')!r}")
        if e["id"] in ids: bad_ids.append(e["id"])
        ids.add(e["id"])
        keys[canonical_event_key({**e,"start":e.get("startUtc")})].append(e)
        expected=event_identity(e.get("league"),e.get("title"),e.get("startUtc"),e.get("home"),e.get("away"))
        if e["id"]!=expected: bad_ids.append(f"{e['id']} != {expected}")
    dup=[(k,v) for k,v in keys.items() if len(v)>1]
    if bad or bad_ids or dup:
        print("INTEGRITY FAILURE")
        for x in bad[:20]: print(" -",x)
        for x in bad_ids[:20]: print(" - duplicate/unstable id:",x)
        for k,v in dup[:20]: print(" - duplicate canonical key:",k,"=>",[e.get("id") for e in v])
        raise SystemExit(1)
    counts=defaultdict(int)
    for e in events: counts[normalize_league(e["league"])] += 1
    print(f"Integrity OK: {len(events)} events, {len(counts)} leagues, {len(ids)} unique IDs")
    print("League counts:",dict(sorted(counts.items())))

if __name__=="__main__": main()
