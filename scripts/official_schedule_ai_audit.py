#!/usr/bin/env python3
"""Authoritative schedule audit used by the Sports Agent.

Every configured official schedule URL is treated as a first-class evidence
source. The audit never fabricates events: only structured Event records
already parsed by the canonical legacy parser are admitted. It is safe to run
frequently because it only adds validated records and never deletes a good
canonical event.
"""
from __future__ import annotations
import argparse, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import refresh_schedules_legacy as engine
from event_identity import identity_match, merge_event_records, event_identity

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
REGISTRY = ROOT / "data" / "official_schedule_sources.json"
MAX_WORKERS = 8


def load_registry():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [x for x in (data.get("officialSources") or []) if x.get("league") and x.get("url")]


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def audit_one(source):
    league = str(source["league"]).strip()
    records = []
    ok, count = engine.add_official_source(records, source)
    # UFC's production page currently publishes event dates in rendered HTML,
    # not JSON-LD. Recover those links without trusting search snippets.
    if league.upper() == "UFC" and not records:
        try:
            import sports_agent
            records.extend(sports_agent._recover_html_schedule(league, source["url"]))
        except Exception:
            pass
    valid = []
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=370)
    for event in records:
        start = parse_time(event.get("start") or event.get("startUtc"))
        title = str(event.get("title") or "").strip()
        if not title or not start or start < now - timedelta(hours=12) or start > horizon:
            continue
        event = dict(event)
        event["league"] = league
        event["source"] = "official"
        event["officialScheduleUrl"] = source["url"]
        event["officialVerifiedAt"] = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        event.setdefault("tag", "UPCOMING")
        valid.append(event)
    return {"league": league, "url": source["url"], "reachable": bool(ok), "parsed": len(valid), "events": valid[:250]}


def merge(events, incoming):
    out = [dict(x) for x in events if isinstance(x, dict)]
    merges = 0
    for candidate in incoming:
        match = next((i for i, existing in enumerate(out) if identity_match(existing, candidate)), None)
        if match is None:
            out.append(candidate)
            continue
        merges += 1
        # Official evidence wins metadata conflicts over older secondary data.
        existing = out[match]
        if str(existing.get("source") or "") != "official":
            out[match] = merge_event_records(candidate, existing)
            out[match]["source"] = "official"
        else:
            out[match] = merge_event_records(existing, candidate)
    for event in out:
        event["id"] = event_identity(event.get("league"), event.get("title"), event.get("start") or event.get("startUtc"), event.get("home"), event.get("away"))
    return out, merges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gaps-only", action="store_true")
    args = ap.parse_args()
    if not FEED.exists():
        raise SystemExit("ERROR: schedule_feed.json does not exist")
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    events = [x for x in (feed.get("events") or []) if isinstance(x, dict)]
    counts = {}
    for e in events:
        counts[str(e.get("league") or "").strip()] = counts.get(str(e.get("league") or "").strip(), 0) + 1
    registry = load_registry()
    if args.gaps_only:
        registry = [x for x in registry if counts.get(str(x["league"]).strip(), 0) == 0]
    results = []
    incoming = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(audit_one, source) for source in registry]
        for future in as_completed(futures):
            result = future.result()
            results.append({k: result[k] for k in ("league", "url", "reachable", "parsed")})
            incoming.extend(result["events"])
    events, merges = merge(events, incoming)
    events.sort(key=lambda e: e.get("start") or e.get("startUtc") or "")
    feed["events"] = events
    feed["eventCounts"] = {}
    for e in events:
        league = str(e.get("league") or "Unknown")
        feed["eventCounts"][league] = feed["eventCounts"].get(league, 0) + 1
    feed["identityMergeCount"] = int(feed.get("identityMergeCount", 0)) + merges
    feed["officialScheduleAudit"] = {
        "enabled": True,
        "mode": "gaps-only" if args.gaps_only else "all-official-sources",
        "sourcesChecked": len(registry),
        "reachableSources": sum(1 for r in results if r["reachable"]),
        "eventsRecovered": len(incoming),
        "identityMerges": merges,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": sorted(results, key=lambda x: x["league"]),
    }
    tmp = FEED.with_suffix(".official-audit.tmp")
    tmp.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(FEED)
    print("OFFICIAL_SCHEDULE_AI_AUDIT: " + json.dumps(feed["officialScheduleAudit"], separators=(",", ":")))


if __name__ == "__main__":
    main()
