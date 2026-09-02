#!/usr/bin/env python3
"""Hydrate and apply deterministic team logos for the remaining leagues.

ESPN is opportunistic only. The five previously failing leagues now have
verified static fallbacks so a provider 403 cannot erase team artwork.
"""
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/team_logo_map.json"
SCHEDULE = ROOT / "data/schedule_feed.json"

LEAGUES = {
    "AFL": ("australian-football", "afl"),
    "NBA": ("basketball", "nba"),
    "NRL": ("rugby-league", "nrl"),
    "PLL": ("lacrosse", "pll"),
    "UEL": ("soccer", "uefa.europa"),
}

ALIASES = {
    "AFL": {
        "Hawthorn": "Hawthorn Hawks", "Fremantle": "Fremantle Dockers",
        "Carlton": "Carlton Blues", "Geelong Cats": "Geelong Cats",
        "Brisbane Lions": "Brisbane Lions", "Sydney Swans": "Sydney Swans",
    },
    "NBA": {
        "Lions": "London Lions", "Los Angeles Clippers": "LA Clippers",
        "LA Lakers": "Los Angeles Lakers", "Golden State": "Golden State Warriors",
        "New Orleans": "New Orleans Pelicans", "Oklahoma City": "Oklahoma City Thunder",
    },
    "NRL": {
        "Broncos": "Brisbane Broncos", "Bulldogs": "Canterbury Bulldogs",
        "Dolphins": "Dolphins", "Titans": "Gold Coast Titans",
        "Roosters": "Sydney Roosters", "Rabbitohs": "South Sydney Rabbitohs",
        "Sea Eagles": "Manly Sea Eagles", "Warriors": "New Zealand Warriors",
        "Raiders": "Canberra Raiders", "Cowboys": "North Queensland Cowboys",
        "Storm": "Melbourne Storm", "Sharks": "Cronulla Sharks",
        "Eels": "Parramatta Eels", "Dragons": "St George Illawarra Dragons",
        "Wests Tigers": "Wests Tigers", "Panthers": "Penrith Panthers",
    },
    "PLL": {
        "Outlaws": "Denver Outlaws", "Archers": "Utah Archers",
        "Cannons": "Boston Cannons", "Waterdogs": "Philadelphia Waterdogs",
    },
    "UEL": {
        "Ferencvaros": "Ferencváros", "Lillestrom": "Lillestrøm",
        "Ararat": "Ararat-Armenia", "Torreense": "Torreense",
    },
}

# Verified, deterministic fallbacks. These are used before any ESPN result is
# required. NRL/PLL URLs are the current official team artwork; AFL/NBA use
# stable Wikimedia files for the named clubs.
STATIC_LOGOS = {
    "AFL": {
        "Hawthorn": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Hawthorn.svg",
        "Fremantle": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Fremantle%20Football%20Club%20Colours.svg",
        "Carlton": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Carlton%20AFL%20icon.svg",
        "Geelong Cats": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Geelong%20icon.svg",
        "Brisbane Lions": "https://commons.wikimedia.org/wiki/Special:Redirect/file/BrisbaneAFL.svg",
        "Sydney Swans": "https://commons.wikimedia.org/wiki/Special:Redirect/file/AFL%20Sydney%20Icon.svg",
    },
    "NBA": {
        "Lions": "https://commons.wikimedia.org/wiki/Special:Redirect/file/London%20Lions%20logo%20%282025%29.png",
        "London Lions": "https://commons.wikimedia.org/wiki/Special:Redirect/file/London%20Lions%20logo%20%282025%29.png",
    },
    "NRL": {
        "Broncos": "https://www.nrl.com/.theme/broncos/badge.svg", "Bulldogs": "https://www.nrl.com/.theme/bulldogs/badge.svg",
        "Dolphins": "https://www.nrl.com/.theme/dolphins/badge.svg", "Titans": "https://www.nrl.com/.theme/titans/badge.svg",
        "Roosters": "https://www.nrl.com/.theme/roosters/badge.svg", "Rabbitohs": "https://www.nrl.com/.theme/rabbitohs/badge.svg",
        "Sea Eagles": "https://www.nrl.com/.theme/sea-eagles/badge.svg", "Warriors": "https://www.nrl.com/.theme/warriors/badge.svg",
        "Raiders": "https://www.nrl.com/.theme/raiders/badge.svg", "Cowboys": "https://www.nrl.com/.theme/cowboys/badge.svg",
        "Storm": "https://www.nrl.com/.theme/storm/badge.svg", "Sharks": "https://www.nrl.com/.theme/sharks/badge.svg",
        "Eels": "https://www.nrl.com/.theme/eels/badge.svg", "Dragons": "https://www.nrl.com/.theme/dragons/badge.svg",
        "Wests Tigers": "https://www.nrl.com/.theme/weststigers/badge.svg", "Panthers": "https://www.nrl.com/.theme/panthers/badge.svg",
    },
    "PLL": {
        "Outlaws": "https://premierlacrosseleague.com/wp-content/uploads/2023/11/denver-crest-1024x681.png",
        "Archers": "https://premierlacrosseleague.com/wp-content/uploads/2023/11/utah-crest-1024x968.png",
        "Cannons": "https://premierlacrosseleague.com/wp-content/uploads/2023/11/boston-crest-1024x971.png",
        "Waterdogs": "https://premierlacrosseleague.com/wp-content/uploads/2023/11/philly-crest-1024x1016.png",
    },
    "UEL": {
        "Torreense": "https://img.uefa.com/imgml/TP/teams/logos/100x100/2603107.png",
    },
}


def norm(value):
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).split())


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "XSportsX/1.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def team_records(payload):
    out = []
    for item in payload.get("sports") or []:
        for league in item.get("leagues") or []:
            for wrapper in league.get("teams") or []:
                team = wrapper.get("team") or wrapper
                if team.get("id") or team.get("displayName"):
                    out.append(team)
    return out


def logo_for(team):
    for candidate in team.get("logos") or []:
        if candidate.get("href"):
            return candidate["href"]
    tid = team.get("id")
    return f"https://a.espncdn.com/i/teamlogos/500/{tid}.png" if tid else None


def add_team(teams, league, team):
    display = team.get("displayName") or team.get("name") or team.get("shortDisplayName")
    logo = logo_for(team)
    if not display or not logo:
        return
    names = {display, team.get("name"), team.get("shortDisplayName"), team.get("location"), team.get("abbreviation"), team.get("slug")}
    if team.get("location") and team.get("name"):
        names.add(f"{team['location']} {team['name']}")
    for name in names:
        if name:
            teams[f"{league}|{norm(name)}"] = logo
    for alias, target in ALIASES.get(league, {}).items():
        if norm(target) == norm(display):
            teams[f"{league}|{norm(alias)}"] = logo


def catalog_for_league(league, sport, slug):
    records = []
    for url in (
        f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=100",
        f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?limit=1000",
    ):
        try:
            payload = get_json(url)
        except Exception as exc:
            print(f"WARNING {league}: {exc}")
            continue
        records.extend(team_records(payload))
        for event in payload.get("events") or []:
            for comp in event.get("competitions") or []:
                for competitor in comp.get("competitors") or []:
                    if competitor.get("team"):
                        records.append(competitor["team"])
    dedup = {}
    for team in records:
        key = str(team.get("id") or team.get("displayName") or team.get("name") or "")
        if key:
            dedup[key] = team
    return list(dedup.values())


def resolve_logo(teams, league, name):
    static = STATIC_LOGOS.get(league, {}).get(name)
    if static:
        return static
    key = f"{league}|{norm(name)}"
    if teams.get(key):
        return teams[key]
    target = ALIASES.get(league, {}).get(name)
    if target and teams.get(f"{league}|{norm(target)}"):
        return teams[f"{league}|{norm(target)}"]
    needle = norm(name)
    matches = [logo for k, logo in teams.items() if k.startswith(f"{league}|") and needle and needle in k.split("|", 1)[1].split()]
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


def hydrate_and_apply():
    data = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"version": 3, "teams": {}}
    teams = data.setdefault("teams", {})
    feed = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    events = feed.get("events") or []
    summary = {}
    for league, (sport, slug) in LEAGUES.items():
        # Static fallbacks are always seeded first, making this path independent
        # of ESPN availability and protecting against future cache regressions.
        for name, logo in STATIC_LOGOS.get(league, {}).items():
            teams[f"{league}|{norm(name)}"] = logo
        records = catalog_for_league(league, sport, slug)
        for team in records:
            add_team(teams, league, team)
        names = {str(e.get(k)) for e in events if e.get("league") == league for k in ("away", "home") if e.get(k)}
        unresolved = []
        changed = 0
        for event in events:
            if event.get("league") != league or event.get("eventType") == "named_event":
                continue
            for side, field in (("away", "awayLogo"), ("home", "homeLogo")):
                name = str(event.get(side) or "")
                logo = resolve_logo(teams, league, name)
                if not logo:
                    unresolved.append(name)
                    continue
                teams[f"{league}|{norm(name)}"] = logo
                if event.get(field) != logo:
                    event[field] = logo
                    changed += 1
        summary[league] = {"espn_records": len(records), "schedule_names": len(names), "unresolved_names": sorted(set(unresolved)), "logo_fields_changed": changed}
        time.sleep(0.1)
    CACHE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    feed["events"] = events
    SCHEDULE.write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    failures = {k: v["unresolved_names"] for k, v in summary.items() if v["unresolved_names"]}
    if failures:
        print("UNRESOLVED:", json.dumps(failures, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    hydrate_and_apply()
