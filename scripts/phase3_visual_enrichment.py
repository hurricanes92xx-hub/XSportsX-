#!/usr/bin/env python3
"""Phase 3: attach presentation metadata to canonical schedule events.

Rules:
- Team-v-team events get best-effort ESPN team logos when the league has an
  ESPN team directory. Never invent a logo: missing teams remain blank so the
  Android renderer can use a safe text fallback.
- Non-team events get league card art and a cleaned event title.
- League card art is stable and lightweight; this runs only during refresh.
- This step never changes event dates or removes events.
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

FEED = Path("data/schedule_feed.json")

LEAGUE_ART = {
    "NFL": "https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png",
    "NBA": "https://a.espncdn.com/i/teamlogos/leagues/500/nba.png",
    "WNBA": "https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png",
    "NCAA FB": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png",
    "NCAA FCS": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png",
    "NCAA BB": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png",
    "NCAA WBB": "https://a.espncdn.com/i/teamlogos/leagues/500/ncaaw.png",
    "MLB": "https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png",
    "NHL": "https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png",
    "MLS": "https://a.espncdn.com/i/teamlogos/leagues/500/mls.png",
    "EPL": "https://a.espncdn.com/i/teamlogos/soccer/500/23.png",
    "LaLiga": "https://a.espncdn.com/i/teamlogos/soccer/500/15.png",
    "Serie A": "https://a.espncdn.com/i/teamlogos/soccer/500/12.png",
    "Bundesliga": "https://a.espncdn.com/i/teamlogos/soccer/500/10.png",
    "Ligue 1": "https://a.espncdn.com/i/teamlogos/soccer/500/9.png",
    "UCL": "https://a.espncdn.com/i/teamlogos/soccer/500/2.png",
    "UEL": "https://a.espncdn.com/i/teamlogos/soccer/500/1.png",
    "NWSL": "https://a.espncdn.com/i/teamlogos/leagues/500/nwsl.png",
    "UFC": "https://commons.wikimedia.org/wiki/Special:FilePath/UFC_Logo.svg?width=256",
    "BOXING": "https://commons.wikimedia.org/wiki/Special:FilePath/World_Boxing_logo_2023.svg?width=256",
    "F1": "https://commons.wikimedia.org/wiki/Special:FilePath/Formula_1_Logo.svg?width=256",
    "NASCAR": "https://commons.wikimedia.org/wiki/Special:FilePath/NASCAR_Logo.svg?width=256",
    "INDYCAR": "https://commons.wikimedia.org/wiki/Special:FilePath/IndyCar_Series_logo.svg?width=256",
    "MotoGP": "https://commons.wikimedia.org/wiki/Special:FilePath/MotoGP_logo_%282024%29.svg?width=256",
    "MXGP": "https://commons.wikimedia.org/wiki/Special:FilePath/Logo_MXGP.svg?width=256",
    "FORMULA E": "https://commons.wikimedia.org/wiki/Special:FilePath/Formula-e-logo-championship_2023.svg?width=256",
    "MONSTER JAM": "https://commons.wikimedia.org/wiki/Special:FilePath/Monster_Jam_logo.svg?width=256",
    "WWE": "https://commons.wikimedia.org/wiki/Special:FilePath/WWE_Official_Logo.svg?width=256",
    "AEW": "https://commons.wikimedia.org/wiki/Special:FilePath/All_Elite_Wrestling_logo.svg?width=256",
    "TNA": "https://commons.wikimedia.org/wiki/Special:FilePath/Total_Nonstop_Action_Wrestling_logo.svg?width=256",
    "AAA Wrestling": "https://commons.wikimedia.org/wiki/Special:FilePath/Lucha_Libre_AAA_Worldwide_logo.svg?width=256",
    "PLL": "https://commons.wikimedia.org/wiki/Special:FilePath/Premier_Lacrosse_League_logo.svg?width=256",
    "NLL": "https://commons.wikimedia.org/wiki/Special:FilePath/National_Lacrosse_League_logo.svg?width=256",
}

ESPN_LEAGUES = {
    "NFL": ("football", "nfl"), "NBA": ("basketball", "nba"), "WNBA": ("basketball", "wnba"),
    "MLB": ("baseball", "mlb"), "NHL": ("hockey", "nhl"), "MLS": ("soccer", "usa.1"),
    "EPL": ("soccer", "eng.1"), "LaLiga": ("soccer", "esp.1"), "Serie A": ("soccer", "ita.1"),
    "Bundesliga": ("soccer", "ger.1"), "Ligue 1": ("soccer", "fra.1"),
}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "XSportsX/Phase3"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)


def norm(s):
    s = str(s or "").upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def split_matchup(title):
    m = re.match(r"^(.+?)\s+@\s+(.+)$", title.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.+?)\s+(?:VS\.?|VERSUS)\s+(.+)$", title.strip(), re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def team_index(league):
    cfg = ESPN_LEAGUES.get(league)
    if not cfg:
        return {}
    sport, slug = cfg
    try:
        data = fetch_json(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/teams?limit=1000")
        rows = (data.get("sports") or [{}])[0].get("leagues") or []
        teams = rows[0].get("teams") if rows else []
        out = {}
        for row in teams or []:
            t = row.get("team") or row
            name = t.get("displayName") or t.get("name") or ""
            logo = t.get("logos", [{}])[0].get("href", "") if t.get("logos") else ""
            if name and logo:
                out[norm(name)] = logo
                if t.get("shortDisplayName"):
                    out[norm(t["shortDisplayName"])] = logo
                if t.get("abbreviation"):
                    out[norm(t["abbreviation"])] = logo
        return out
    except Exception as exc:
        print(f"PHASE3 logo lookup unavailable for {league}: {exc}")
        return {}


def clean_event_title(event):
    title = str(event.get("title") or "").strip()
    if title:
        return title
    away = str(event.get("away") or "").strip()
    home = str(event.get("home") or "").strip()
    if away and home:
        return f"{away} @ {home}"
    return str(event.get("league") or "Sports Event").strip()


def main():
    payload = json.loads(FEED.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    indexes = {league: team_index(league) for league in ESPN_LEAGUES}
    team_logos = 0
    league_art = 0
    cleaned = 0
    non_team = 0

    for event in events:
        league = str(event.get("league") or "").strip()
        old_title = event.get("title", "")
        title = clean_event_title(event)
        if title != old_title:
            cleaned += 1
        event["title"] = title
        event["leagueArt"] = LEAGUE_ART.get(league, "")
        if event["leagueArt"]:
            league_art += 1
        event["eventType"] = "team_game"

        away, home = split_matchup(title)
        if not away and not home:
            away = str(event.get("away") or "").strip()
            home = str(event.get("home") or "").strip()
        if away and home:
            event["away"] = away
            event["home"] = home
            idx = indexes.get(league, {})
            event["awayLogo"] = event.get("awayLogo") or idx.get(norm(away), "")
            event["homeLogo"] = event.get("homeLogo") or idx.get(norm(home), "")
            if event["awayLogo"] or event["homeLogo"]:
                team_logos += int(bool(event["awayLogo"])) + int(bool(event["homeLogo"]))
        else:
            event["eventType"] = "named_event"
            non_team += 1
            # Non-team cards deliberately use the league art instead of a fake
            # competitor logo. Keep any genuine event image if already supplied.
            if not event.get("image") and event["leagueArt"]:
                event["image"] = event["leagueArt"]

    report = payload.setdefault("phase3VisualReport", {})
    report.update({
        "version": 1,
        "events": len(events),
        "team_logo_fields_populated": team_logos,
        "league_art_fields_populated": league_art,
        "named_events": non_team,
        "titles_cleaned": cleaned,
        "rule": "no invented team logos; named-event cards use league art",
    })
    payload["phase3Visuals"] = True
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
