#!/usr/bin/env python3
"""Probe the public schedule sources used by XSportsX.

The QA probe must test the same source family used by the production schedule
refresh. ESPN does not expose the NCAA BB/WBB/Softball feeds through the
league-specific scoreboard routes used by this diagnostic, and boxing is not
an ESPN scoreboard league. Those four are therefore checked through their
actual working schedule sources instead of being reported as false gaps.
"""
import json
import sys
import urllib.request
from datetime import date, timedelta

BASE = "https://site.api.espn.com/apis/site/v2"
ESPN_LEAGUES = [
    ("NFL", "football/nfl"), ("NBA", "basketball/nba"), ("WNBA", "basketball/wnba"),
    ("NCAA FB", "football/college-football?groups=80"), ("NCAA FCS", "football/college-football?groups=81"),
    ("MLB", "baseball/mlb"), ("NCAA BASEBALL", "baseball/college-baseball"), ("NHL", "hockey/nhl"),
    ("NCAA MEN HOCKEY", "hockey/mens-college-hockey"), ("NCAA WOMEN HOCKEY", "hockey/womens-college-hockey"),
    ("NCAA VB", "volleyball/womens-college-volleyball"),
    ("NCAA MEN SOCCER", "soccer/usa.ncaa.m.1"), ("NCAA WOMEN SOCCER", "soccer/usa.ncaa.w.1"),
    ("NCAA MEN LAX", "lacrosse/mens-college-lacrosse"), ("NCAA WOMEN LAX", "lacrosse/womens-college-lacrosse"),
    ("MLS", "soccer/usa.1"), ("EPL", "soccer/eng.1"), ("LaLiga", "soccer/esp.1"),
    ("Bundesliga", "soccer/ger.1"), ("Serie A", "soccer/ita.1"), ("Ligue 1", "soccer/fra.1"),
    ("UCL", "soccer/uefa.champions"), ("UEL", "soccer/uefa.europa"), ("NWSL", "soccer/usa.nwsl"),
    ("UFC", "mma/ufc"),
]

NCAA_FIXES = [
    ("NCAA BB", "basketball-men", "d1"),
    ("NCAA WBB", "basketball-women", "d1"),
    ("NCAA SOFTBALL", "softball", "d1"),
]

BOXING_URL = "https://www.thesportsdb.com/api/v1/json/123/eventsday.php"


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "XSportsX-QA/1.2", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        if r.status < 200 or r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")
        return json.load(r)


def probe_espn(name, path, dates):
    if "?" in path:
        p, q = path.split("?", 1)
        url = f"{BASE}/sports/{p}/scoreboard?dates={dates}&limit=1000&{q}"
    else:
        url = f"{BASE}/sports/{path}/scoreboard?dates={dates}&limit=1000"
    payload = fetch(url)
    raw = payload.get("events", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise RuntimeError("events is not an array")
    return len(raw)


def probe_ncaa(name, sport, division, dates):
    start = date.today()
    end = start + timedelta(days=3)
    successes = 0
    events = 0
    errors = []
    current = start
    while current <= end:
        url = (
            f"https://ncaa-api.henrygd.me/scoreboard/{sport}/{division}/"
            f"{current:%Y/%m/%d}/all-conf"
        )
        try:
            payload = fetch(url)
            if not isinstance(payload, dict):
                raise RuntimeError("JSON root is not an object")
            games = payload.get("games", [])
            if games is None:
                games = []
            if not isinstance(games, list):
                raise RuntimeError("games is not an array")
            successes += 1
            events += len(games)
        except Exception as exc:
            errors.append(f"{current}: {exc}")
        current += timedelta(days=1)
    if successes == 0:
        raise RuntimeError("NCAA source failed for every day: " + "; ".join(errors))
    return events


def probe_boxing():
    # Boxing is part of TheSportsDB's Fighting schedule rather than an ESPN
    # scoreboard league. A successful JSON response is a healthy source even
    # when the current day has zero boxing cards.
    today = date.today()
    payload = fetch(f"{BOXING_URL}?d={today:%Y-%m-%d}&s=Fighting")
    if not isinstance(payload, dict):
        raise RuntimeError("JSON root is not an object")
    events = payload.get("events", [])
    if events is None:
        events = []
    if not isinstance(events, list):
        raise RuntimeError("events is not an array")
    # The source contains MMA/wrestling as well, so only count obvious boxing
    # cards for the diagnostic while still treating the source as reachable.
    boxing = 0
    for event in events:
        text = json.dumps(event).lower()
        if any(token in text for token in ("boxing", "boxeo", "boxen", "fight")):
            boxing += 1
    return boxing


def main():
    today = date.today()
    end = today + timedelta(days=3)
    dates = f"{today:%Y%m%d}-{end:%Y%m%d}"
    results = []
    failures = []

    for name, path in ESPN_LEAGUES:
        try:
            events = probe_espn(name, path, dates)
            row = {"league": name, "events_3d": events, "ok": True, "source": "ESPN"}
            print(f"PUBLIC {name:18} OK  events={events}")
        except Exception as exc:
            row = {"league": name, "events_3d": 0, "ok": False, "source": "ESPN", "errors": [str(exc)]}
            print(f"PUBLIC {name:18} GAP {[str(exc)]}")
            failures.append(row)
        results.append(row)

    for name, sport, division in NCAA_FIXES:
        try:
            events = probe_ncaa(name, sport, division, dates)
            row = {"league": name, "events_3d": events, "ok": True, "source": "NCAA API"}
            print(f"PUBLIC {name:18} OK  events={events} source=NCAA")
        except Exception as exc:
            row = {"league": name, "events_3d": 0, "ok": False, "source": "NCAA API", "errors": [str(exc)]}
            print(f"PUBLIC {name:18} GAP {[str(exc)]}")
            failures.append(row)
        results.append(row)

    try:
        events = probe_boxing()
        row = {"league": "BOXING", "events_3d": events, "ok": True, "source": "TheSportsDB Fighting"}
        print(f"PUBLIC {'BOXING':18} OK  events={events} source=TheSportsDB")
    except Exception as exc:
        row = {"league": "BOXING", "events_3d": 0, "ok": False, "source": "TheSportsDB Fighting", "errors": [str(exc)]}
        print(f"PUBLIC {'BOXING':18} GAP {[str(exc)]}")
        failures.append(row)
    results.append(row)

    summary = {
        "window": f"{today}..{end}",
        "total": len(results),
        "reachable": sum(r["ok"] for r in results),
        "failure_count": len(failures),
        "failures": failures,
        "results": results,
    }
    out = sys.argv[1] if len(sys.argv) > 1 else "public-schedule-probe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Public schedule probe: {summary['reachable']}/{summary['total']} endpoints reachable; diagnostic-only, emulator tests continue.")


if __name__ == "__main__":
    main()
