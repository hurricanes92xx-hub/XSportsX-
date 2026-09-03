#!/usr/bin/env python3
"""Canonical schedule refresh using a persistent league/provider health matrix."""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import refresh_schedules_legacy as engine
from event_identity import identity_match, merge_event_records, event_identity, normalize_league
from provider_health import build_matrix, provider_order, record
from providers.ncaa import ESPN_FALLBACK as NCAA_ESPN

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "schedule_feed.json"


def official_map():
    result = {}
    for source in engine.load_official_registry():
        league = str(source.get("league") or "").strip()
        if league: result.setdefault(league, []).append(source)
    return result


def icon_map():
    result = {x[0]: x[3] for x in engine.ESPN_LEAGUES}
    result.update({x[0]: x[3] for x in engine.NCAA_LEAGUES})
    result.update({x: "🏎️" for x in engine.NASCAR_SERIES})
    result.update({"WWE": "🏆", "AEW": "🤼", "TNA": "🤼"})
    return result


def dedupe(events):
    priority = {"official": 0, "ncaa": 1, "nascar": 1, "espn": 2, "espn-ncaa": 2, "sportsdb": 3, "fallback": 4, "cache": 5}
    canonical, merges, counts = [], 0, {}
    for raw in events:
        candidate = dict(raw); source = candidate.get("source") or "unknown"
        counts[source] = counts.get(source, 0) + 1
        match = next((i for i, existing in enumerate(canonical) if identity_match(existing, candidate)), None)
        if match is None:
            canonical.append(candidate); continue
        merges += 1; existing = canonical[match]
        if priority.get(source, 9) < priority.get(existing.get("source"), 9):
            winner = merge_event_records(candidate, existing); winner["source"] = source; canonical[match] = winner
        else:
            canonical[match] = merge_event_records(existing, candidate)
    for event in canonical:
        event["id"] = event_identity(event.get("league"), event.get("title"), event.get("start"), event.get("home"), event.get("away"))
    return canonical, merges, counts


def fetch(provider, league, meta, officials, previous):
    try:
        if provider == "official":
            events = []; ok = False
            for source in officials.get(league, []):
                part = []; source_ok, _ = engine.add_official_source(part, source)
                ok = ok or source_ok; events.extend(part)
            return ok and bool(events), events, ""
        if provider == "espn":
            row = meta.get("espn")
            if not row: return False, [], "not configured"
            events = []; ok, _ = engine.add_espn(events, league, *row)
            return bool(ok and events), events, ""
        if provider == "ncaa":
            row = meta.get("ncaa")
            if not row: return False, [], "not configured"
            events = engine.fetch_ncaa_league(league, *row, horizon_days=30)
            return bool(events), events, ""
        if provider == "espn-ncaa":
            mapping = NCAA_ESPN.get(league)
            if not mapping: return False, [], "not configured"
            events = []; ok, _ = engine.add_espn(events, league, mapping[0], mapping[1], meta["icon"], 30)
            for event in events: event["source"] = "espn-ncaa"
            return bool(ok and events), events, ""
        if provider == "nascar":
            events = engine.fetch_nascar_league(league, horizon_days=370)
            return bool(events), events, ""
        if provider == "sportsdb":
            events = []; ok, _ = engine.add_sportsdb(events, league, meta["icon"])
            return bool(ok and events), events, ""
        if provider == "cache":
            events = [dict(e, source="cache") for e in previous if normalize_league(e.get("league")) == normalize_league(league)]
            return bool(events), events, "cache"
        return False, [], "unknown provider"
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"[:300]


def main():
    previous = {}
    if OUT.exists():
        try: previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception: previous = {}
    previous_events = previous.get("events") or []
    officials = official_map(); icons = icon_map()
    espn = {x[0]: x[1:] for x in engine.ESPN_LEAGUES}
    ncaa = {x[0]: x[1:] for x in engine.NCAA_LEAGUES}
    dedicated_names = set(ncaa) | set(engine.NASCAR_SERIES)
    official_names = set(officials); sportsdb_names = set(engine.SPORTDB_LEAGUES)
    all_leagues = official_names | set(espn) | dedicated_names | sportsdb_names | {"WWE", "AEW", "TNA"}
    dedicated = {name: ("ncaa" if name in ncaa else "nascar") for name in dedicated_names}
    matrix = build_matrix(all_leagues, official_names, dedicated, set(espn), sportsdb_names)

    events = []; failures = []; attempts = {}; promotions = {}; cache_recovery = []
    for league in sorted(all_leagues):
        configured = matrix[league]["configured"]
        ordered = provider_order(league, configured)
        matrix[league]["activeOrder"] = ordered
        attempts[league] = []
        meta = {"icon": icons.get(league, "🏆"), "espn": espn.get(league), "ncaa": ncaa.get(league)}
        selected = None
        for provider in ordered:
            started = time.monotonic()
            ok, got, error = fetch(provider, league, meta, officials, previous_events)
            latency = round((time.monotonic() - started) * 1000, 1)
            attempts[league].append({"provider": provider, "ok": ok, "events": len(got), "latencyMs": latency, "error": error})
            record(league, provider, ok, len(got), latency, error)
            if ok and got:
                selected = provider; events.extend(got); break
        if selected is None:
            failures.append(league); continue
        promotions[league] = selected
        if selected == "cache": cache_recovery.append(league)
        if ordered and selected != ordered[0]:
            matrix[league]["promotedFrom"] = ordered[0]
            matrix[league]["promotedTo"] = selected

    wrestling = []; engine.add_wrestling(wrestling); events.extend(wrestling)
    events, merges, source_counts = dedupe(events)
    events = sorted(events, key=lambda e: e.get("start", ""))
    per = {}
    for event in events: per[event.get("league", "Unknown")] = per.get(event.get("league", "Unknown"), 0) + 1
    promoted_count = sum(1 for value in matrix.values() if value.get("promotedTo"))
    payload = {
        "schema": 9,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshHours": 6,
        "eventCounts": per,
        "failedSources": failures,
        "providerFailures": failures,
        "sportsDbFallbackSources": [],
        "officialSourceFailures": [],
        "officialSourceCounts": {},
        "identityMergeCount": merges,
        "sourceRecordCounts": source_counts,
        "leagueProviderMatrix": matrix,
        "providerAttempts": attempts,
        "providerPromotions": promotions,
        "cacheRecoveryLeagues": cache_recovery,
        "events": events,
    }
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(OUT)
    print(f"wrote {len(events)} canonical events across {len(per)} leagues; matrix={len(matrix)}; promotions={promoted_count}; cache={len(cache_recovery)}; identity_merges={merges}")

if __name__ == "__main__": main()
