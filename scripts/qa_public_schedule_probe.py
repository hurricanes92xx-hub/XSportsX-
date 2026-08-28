#!/usr/bin/env python3
"""Probe the same public ESPN schedule endpoints used by XSportsX.
No credentials and no private provider access are used. Zero-event leagues are
reported as seasonal/no-events rather than failures; HTTP/JSON/schema failures fail QA.
"""
import json
import sys
import time
import urllib.request
from datetime import date, timedelta

BASES = [
    "https://site.api.espn.com/apis/site/v2",
    "https://site.api.espn.com/apis/site/v3",
]
LEAGUES = [
    ("NFL", "football/nfl"), ("NBA", "basketball/nba"), ("WNBA", "basketball/wnba"),
    ("NCAA FB", "football/college-football?groups=80"), ("NCAA FCS", "football/college-football?groups=81"),
    ("NCAA BB", "basketball/mens-college-basketball"), ("NCAA WBB", "basketball/womens-college-basketball"),
    ("MLB", "baseball/mlb"), ("NCAA BASEBALL", "baseball/college-baseball"), ("NHL", "hockey/nhl"),
    ("NCAA MEN HOCKEY", "hockey/mens-college-hockey"), ("NCAA WOMEN HOCKEY", "hockey/womens-college-hockey"),
    ("NCAA SOFTBALL", "softball/college-softball"), ("NCAA VB", "volleyball/womens-college-volleyball"),
    ("NCAA MEN SOCCER", "soccer/usa.ncaa.m.1"), ("NCAA WOMEN SOCCER", "soccer/usa.ncaa.w.1"),
    ("NCAA MEN LAX", "lacrosse/mens-college-lacrosse"), ("NCAA WOMEN LAX", "lacrosse/womens-college-lacrosse"),
    ("MLS", "soccer/usa.1"), ("EPL", "soccer/eng.1"), ("LaLiga", "soccer/esp.1"),
    ("Bundesliga", "soccer/ger.1"), ("Serie A", "soccer/ita.1"), ("Ligue 1", "soccer/fra.1"),
    ("UCL", "soccer/uefa.champions"), ("UEL", "soccer/uefa.europa"), ("NWSL", "soccer/usa.nwsl"),
    ("UFC", "mma/ufc"), ("BOXING", "boxing/boxing"),
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "XSportsX-QA/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        if r.status < 200 or r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")
        return json.load(r)

def main():
    today = date.today(); end = today + timedelta(days=7)
    dates = f"{today:%Y%m%d}-{end:%Y%m%d}"
    results = []
    failures = []
    for name, path in LEAGUES:
        ok = False; events = 0; errors = []
        for base in BASES:
            # path may contain query parameters for NCAA grouping.
            if "?" in path:
                p, q = path.split("?", 1)
                url = f"{base}/sports/{p}/scoreboard?dates={dates}&limit=1000&{q}"
            else:
                url = f"{base}/sports/{path}/scoreboard?dates={dates}&limit=1000"
            try:
                payload = fetch(url)
                if not isinstance(payload, dict):
                    raise RuntimeError("JSON root is not an object")
                raw = payload.get("events", [])
                if raw is None: raw = []
                if not isinstance(raw, list):
                    raise RuntimeError("events is not an array")
                events = max(events, len(raw)); ok = True
                break
            except Exception as exc:
                errors.append(f"{base.split('/apis/')[1]}: {exc}")
        row = {"league": name, "events_7d": events, "ok": ok, "errors": errors}
        results.append(row)
        if not ok: failures.append(row)
        print(f"PUBLIC {name:18} {'OK':3} events={events}" if ok else f"PUBLIC {name:18} FAIL {errors}")

    summary = {"window": f"{today}..{end}", "total": len(results), "reachable": sum(r["ok"] for r in results), "failures": failures, "results": results}
    out = sys.argv[1] if len(sys.argv) > 1 else "public-schedule-probe.json"
    with open(out, "w") as f: json.dump(summary, f, indent=2)
    print(f"Public schedule probe: {summary['reachable']}/{summary['total']} endpoints reachable; zero-event leagues are allowed.")
    if failures: sys.exit(1)

if __name__ == "__main__": main()
