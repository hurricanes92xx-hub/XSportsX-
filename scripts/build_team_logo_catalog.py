#!/usr/bin/env python3
"""Build the persistent team-logo cache outside the schedule refresh.

This job is intentionally separate from refresh_schedules_engine.py. It may make
slow external catalog requests, but the normal schedule refresh never does.

ESPN's public team catalog exposes current team names, abbreviations and logo URLs.
We turn those catalogs into the normalized lookup keys consumed by
phase3_visual_enrichment.py. The resulting JSON contains only small text URLs;
we do not download image binaries.

IMPORTANT: ESPN's site teams endpoint silently caps the response around 50 rows
when a large limit is requested through the old page-based implementation. The
correct approach is a single large `limit` request (up to the catalog size), not
`page=1,2,...`. The old implementation therefore left NCAA catalogs at 50 teams.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "team_logo_map.json"

HEADERS = {
    "User-Agent": "XSportsX-TeamLogoCatalog/1.0",
    "Accept": "application/json,text/plain,*/*",
}

LEAGUES = {
    "NFL": ("football", "nfl"), "NBA": ("basketball", "nba"), "WNBA": ("basketball", "wnba"),
    "MLB": ("baseball", "mlb"), "NHL": ("hockey", "nhl"), "MLS": ("soccer", "usa.1"),
    "EPL": ("soccer", "eng.1"), "LaLiga": ("soccer", "esp.1"), "Serie A": ("soccer", "ita.1"),
    "Bundesliga": ("soccer", "ger.1"), "Ligue 1": ("soccer", "fra.1"),
    "UCL": ("soccer", "uefa.champions"), "UEL": ("soccer", "uefa.europa"), "NWSL": ("soccer", "usa.nwsl"),
    "NCAA FB": ("football", "college-football"), "NCAA FCS": ("football", "college-football"),
    "NCAA BB": ("basketball", "mens-college-basketball"), "NCAA WBB": ("basketball", "womens-college-basketball"),
    "NCAA Baseball": ("baseball", "college-baseball"), "NCAA Softball": ("softball", "college-softball"),
    "NCAA Men's Hockey": ("hockey", "mens-college-hockey"), "NCAA Women's Hockey": ("hockey", "womens-college-hockey"),
    "NCAA Men's Soccer": ("soccer", "usa.ncaa.m.1"), "NCAA Women's Soccer": ("soccer", "usa.ncaa.w.1"),
    "NCAA Men's Volleyball": ("volleyball", "mens-college-volleyball"), "NCAA Women's Volleyball": ("volleyball", "womens-college-volleyball"),
    "NCAA Women's Field Hockey": ("field-hockey", "ncaa.womens.field.hockey"),
}

MLB_ALIASES = {
    "LAA": ["LA ANGELS", "ANGELS"], "LAD": ["LA DODGERS", "DODGERS"], "ARI": ["AZ", "ARIZONA", "DIAMONDBACKS", "D BACKS"],
    "ATL": ["ATLANTA", "BRAVES"], "BAL": ["BALTIMORE", "ORIOLES"], "BOS": ["BOSTON", "RED SOX"],
    "CHC": ["CHICAGO CUBS", "CUBS"], "CHW": ["CWS", "CHICAGO WHITE SOX", "WHITE SOX"], "CIN": ["CINCINNATI", "REDS"],
    "CLE": ["CLEVELAND", "GUARDIANS"], "COL": ["COLORADO", "ROCKIES"], "DET": ["DETROIT", "TIGERS"],
    "HOU": ["HOUSTON", "ASTROS"], "KC": ["KANSAS CITY", "KANSAS CITY ROYALS", "ROYALS"], "MIA": ["MIAMI", "MARLINS"],
    "MIL": ["MILWAUKEE", "BREWERS"], "MIN": ["MINNESOTA", "TWINS"], "NYM": ["NY METS", "NEW YORK METS", "METS"],
    "NYY": ["NY YANKEES", "NEW YORK YANKEES", "YANKEES"], "PHI": ["PHILADELPHIA", "PHILLIES"], "PIT": ["PITTSBURGH", "PIRATES"],
    "SD": ["SAN DIEGO", "SD PADRES", "PADRES"], "SF": ["SAN FRANCISCO", "SF GIANTS", "GIANTS"], "SEA": ["SEATTLE", "MARINERS"],
    "STL": ["ST LOUIS", "ST. LOUIS", "CARDINALS"], "TB": ["TAMPA BAY", "TB RAYS", "RAYS"], "TEX": ["TEXAS", "RANGERS"],
    "TOR": ["TORONTO", "BLUE JAYS"], "WSH": ["WASHINGTON", "NATIONALS"], "ATH": ["ATHLETICS", "ATHS"],
}


def norm(value: str) -> str:
    value = str(value or "").upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def extract_teams(root):
    out = []
    sports = root.get("sports") if isinstance(root, dict) else None
    if isinstance(sports, list):
        for sport in sports:
            for league in sport.get("leagues") or []:
                out.extend(league.get("teams") or [])
    if not out and isinstance(root, dict):
        out.extend(root.get("teams") or [])
    normalized = []
    for item in out:
        team = item.get("team") if isinstance(item, dict) else item
        if not isinstance(team, dict):
            continue
        logos = team.get("logos") or []
        logo = str(logos[0].get("href") or "").strip() if logos and isinstance(logos[0], dict) else ""
        if not logo:
            continue
        names = {team.get("displayName"), team.get("shortDisplayName"), team.get("name"), team.get("abbreviation"), team.get("slug")}
        names = [norm(x) for x in names if x]
        normalized.append((team, logo, sorted(set(x for x in names if x))))
    return normalized


def fetch_all_teams(base_url: str):
    """Fetch the complete catalog in one request.

    The ESPN site API supports a large `limit` for this endpoint. Its `page`
    parameter is not reliable for these catalog responses and was the reason
    the previous implementation repeatedly received the same first 50 teams.
    """
    root = fetch_json(f"{base_url}?limit=1000")
    rows = extract_teams(root)
    if not rows:
        raise RuntimeError(f"ESPN returned no teams for {base_url}")
    return rows


def main():
    cache = {"version": 3, "teams": {}, "sources": {}, "generatedAt": None}
    if CACHE.exists():
        try:
            old = json.loads(CACHE.read_text(encoding="utf-8"))
            if isinstance(old, dict):
                cache["teams"].update(old.get("teams") or {})
        except Exception:
            pass

    report = {}
    for league, (sport, slug) in LEAGUES.items():
        base_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams"
        try:
            rows = fetch_all_teams(base_url)
            added = 0
            for team, logo, names in rows:
                for name in names:
                    key = f"{league}|{name}"
                    if cache["teams"].get(key) != logo:
                        cache["teams"][key] = logo
                        added += 1
                if league == "MLB":
                    code = norm(team.get("abbreviation") or "")
                    for alias in MLB_ALIASES.get(code, []):
                        key = f"MLB|{norm(alias)}"
                        if cache["teams"].get(key) != logo:
                            cache["teams"][key] = logo
                            added += 1
            cache["sources"][league] = {"provider": "ESPN team catalog", "url": base_url, "teams": len(rows), "completeCatalog": True}
            report[league] = {"status": "ok", "teams": len(rows), "keys_added_or_updated": added}
        except Exception as exc:
            report[league] = {"status": "error", "error": str(exc)}
        time.sleep(0.25)

    from datetime import datetime, timezone
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in report.values() if r.get("status") == "ok")
    print(json.dumps({"version": 3, "leagues_ok": ok, "leagues_total": len(LEAGUES), "cache_entries": len(cache["teams"]), "report": report}, indent=2, sort_keys=True))


if __name__ == "__main__":main()
