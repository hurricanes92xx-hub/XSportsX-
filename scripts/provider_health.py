#!/usr/bin/env python3
"""Persist provider health for the hot schedule lane."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "schedule_feed.json"
HEALTH = ROOT / "data" / "provider_health.json"

ESPN_LEAGUES = {
    "NFL","NCAA FB","CFL","NBA","WNBA","NCAA BB","NCAA WBB","MLB",
    "NCAA BASEBALL","NHL","NCAA MEN HOCKEY","NCAA WOMEN HOCKEY","NCAA SOFTBALL",
    "MLS","NWSL","NCAA Men Soccer","NCAA Women Soccer","EPL","UCL","UEL",
    "LaLiga","Serie A","Bundesliga","Ligue 1","UFC","F1","IndyCar","NASCAR Cup",
    "PGA","LPGA","LIV Golf","ATP","WTA","PLL","NLL","NCAA MEN LAX",
    "NCAA WOMEN LAX","FIVB Men","FIVB Women","NCAA VB","NRL","AFL","ICC T20","IPL",
}

def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def main():
    feed = json.loads(FEED.read_text(encoding="utf-8"))
    report = feed.get("repairReport") or {}
    failed_raw = set(str(x) for x in (report.get("liveFailedProviders") or []))
    failed_leagues = {x.split(":", 1)[0] for x in failed_raw if ":" in x}
    failed_stats = "MLB Stats API" in failed_raw
    stamp = utc_now()
    health = json.loads(HEALTH.read_text(encoding="utf-8")) if HEALTH.exists() else {"schema": 1, "providers": {}}
    providers = health.setdefault("providers", {})
    events = feed.get("events") or []

    for league in sorted(ESPN_LEAGUES):
        key = f"espn:{league}"
        item = providers.setdefault(key, {"consecutiveFailures": 0})
        item["checkedAt"] = stamp
        item["eventsInFeed"] = sum(1 for e in events if e.get("league") == league)
        if league in failed_leagues:
            item["status"] = "degraded"
            item["lastFailureAt"] = stamp
            item["consecutiveFailures"] = int(item.get("consecutiveFailures", 0)) + 1
        else:
            item["status"] = "healthy"
            item["lastSuccessAt"] = stamp
            item["consecutiveFailures"] = 0

    item = providers.setdefault("mlb:stats-api", {"consecutiveFailures": 0})
    item["checkedAt"] = stamp
    item["eventsInFeed"] = sum(1 for e in events if e.get("league") == "MLB")
    if failed_stats:
        item["status"] = "degraded"
        item["lastFailureAt"] = stamp
        item["consecutiveFailures"] = int(item.get("consecutiveFailures", 0)) + 1
    else:
        item["status"] = "healthy"
        item["lastSuccessAt"] = stamp
        item["consecutiveFailures"] = 0

    health["schema"] = 1
    health["updatedAt"] = stamp
    health["lastLiveReconciliation"] = {
        "statusUpdates": int(report.get("liveStatusReconciled", 0) or 0),
        "eventsAdded": int(report.get("liveEventsAdded", 0) or 0),
        "providerFailures": int(report.get("liveProviderFailures", 0) or 0),
        "failedProviders": sorted(failed_raw),
    }
    tmp = HEALTH.with_suffix(".tmp")
    tmp.write_text(json.dumps(health, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(HEALTH)

    failed_count = len(failed_leagues) + (1 if failed_stats else 0)
    authority_count = len(ESPN_LEAGUES) + 1
    if failed_count >= authority_count:
        raise SystemExit("LIVE HEALTH REJECTED: every live authority failed; retaining last known-good state")
    print(f"PROVIDER HEALTH: {authority_count - failed_count}/{authority_count} authorities healthy")

if __name__ == "__main__":
    main()
