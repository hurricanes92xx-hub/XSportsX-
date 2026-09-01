#!/usr/bin/env python3
"""Build the persistent team-logo cache outside the schedule refresh.

This job is intentionally separate from refresh_schedules_engine.py. It may make
slow external catalog requests, but the normal schedule refresh never does.

ESPN's public team catalog exposes current team names, abbreviations and logo
URLs. We turn those catalogs into the exact normalized lookup keys consumed by
phase3_visual_enrichment.py. The resulting JSON contains only small text URLs;
we do not download image binaries.
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

# League key -> ESPN sport/league slug. These are catalog endpoints only.
LEAGUES = {
    "NFL": ("football", "nfl"),
    "NBA": ("basketball", "nba"),
    "WNBA": ("basketball", "wnba"),
    "MLB": ("baseball", "mlb"),
    "NHL": ("hockey", "nhl"),
    "MLS": ("soccer", "usa.1"),
    "EPL": ("soccer", "eng.1"),
    "LaLiga": ("soccer", "esp.1"),
    "Serie A": ("soccer", "ita.1"),
    "Bundesliga": ("soccer", "ger.1"),
    "Ligue 1": ("soccer", "fra.1"),
    "UCL": ("soccer", "uefa.champions"),
    "UEL": ("soccer", "uefa.europa"),
    "NWSL": ("soccer", "usa.nwsl"),
    "NCAA FB": ("football", "college-football"),
    "NCAA FCS": ("football", "college-football"),
    "NCAA BB": ("basketball", "mens-college-basketball"),
    "NCAA WBB": ("basketball", "womens-college-basketball"),
    "NCAA Baseball": ("baseball", "college-baseball"),
    "NCAA Softball": ("softball", "college-softball"),
    "NCAA Men's Hockey": ("hockey", "mens-college-hockey"),
    "NCAA Women's Hockey": ("hockey", "womens-college-hockey"),
    "NCAA Men's Soccer": ("soccer", "usa.ncaa.m.1"),
    "NCAA Women's Soccer": ("soccer", "usa.ncaa.w.1"),
    "NCAA Men's Volleyball": ("volleyball", "mens-college-volleyball"),
    "NCAA Women's Volleyball": ("volleyball", "womens-college-volleyball"),
    "NCAA Women's Field Hockey": ("field-hockey", "ncaa.womens.field.hockey"),
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
    # ESPN site API normally returns sports -> leagues -> teams, but tolerate
    # the alternate wrapper shapes used by a few endpoints.
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
        logo = ""
        if logos and isinstance(logos[0], dict):
            logo = str(logos[0].get("href") or "").strip()
        if not logo:
            continue
        names = {
            team.get("displayName"),
            team.get("shortDisplayName"),
            team.get("name"),
            team.get("abbreviation"),
            team.get("slug"),
        }
        names = [norm(x) for x in names if x]
        normalized.append((team, logo, sorted(set(x for x in names if x))))
    return normalized


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
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams"
        try:
            root = fetch_json(url)
            rows = extract_teams(root)
            added = 0
            for team, logo, names in rows:
                for name in names:
                    key = f"{league}|{name}"
                    if cache["teams"].get(key) != logo:
                        cache["teams"][key] = logo
                        added += 1
            cache["sources"][league] = {"provider": "ESPN team catalog", "url": url, "teams": len(rows)}
            report[league] = {"status": "ok", "teams": len(rows), "keys_added_or_updated": added}
        except Exception as exc:
            report[league] = {"status": "error", "error": str(exc)}
        time.sleep(0.25)

    from datetime import datetime, timezone
    cache["generatedAt"] = datetime.now(timezone.utc).isoformat()
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    ok = sum(1 for r in report.values() if r.get("status") == "ok")
    print(json.dumps({"version": 3, "leagues_ok": ok, "leagues_total": len(LEAGUES), "cache_entries": len(cache["teams"]), "report": report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
