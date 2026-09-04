"""Provider-package override for the legacy free.py module.

Python resolves a regular package before a same-named source file, so this keeps the
existing provider implementations while giving cricket a dedicated, resilient path.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import urllib.request, json, urllib.parse
from datetime import datetime, timezone

_LEGACY_PATH = Path(__file__).resolve().parents[1] / "free.py"
_spec = importlib.util.spec_from_file_location("_xsportsx_free_legacy", _LEGACY_PATH)
_legacy = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_legacy)
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_CRICKET_HEADERS = {"User-Agent":"XSportsX-Schedule/1.1","Accept":"application/json"}

def _json(url, timeout=8):
    req = urllib.request.Request(url, headers=_CRICKET_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))

def _norm(value):
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())

def _iso(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(value)

def _event_from_espn(event, league, source="espn-cricket-core"):
    if not isinstance(event, dict):
        return None
    competitions = event.get("competitions") or []
    comp = competitions[0] if isinstance(competitions, list) and competitions else {}
    teams = comp.get("competitors") or event.get("competitors") or []
    home = next((x.get("team", {}).get("displayName") or x.get("team", {}).get("shortDisplayName") for x in teams if x.get("homeAway") == "home"), "")
    away = next((x.get("team", {}).get("displayName") or x.get("team", {}).get("shortDisplayName") for x in teams if x.get("homeAway") == "away"), "")
    start = event.get("date") or event.get("startDate") or event.get("startTime")
    if not start:
        return None
    state = str(((comp.get("status") or {}).get("type") or {}).get("state") or event.get("status") or "pre").lower()
    tag = "LIVE" if state == "in" else "FINAL" if state in {"post", "final", "complete", "completed"} else "UPCOMING"
    title = f"{away} @ {home}" if home and away else str(event.get("name") or event.get("shortName") or league)
    return {"league":league,"title":title,"start":_iso(start),"tag":tag,"icon":"🏏","source":source,"home":home,"away":away,"providerEventId":f"espn:{event.get('id') or start}"}

def _cricket_core(league):
    league_id = {"IPL":"ipl", "ICC T20":"icc.t20"}.get(league)
    if not league_id:
        return True, []
    out=[]; seen=set()
    try:
        url=f"https://sports.core.api.espn.com/v2/sports/cricket/leagues/{urllib.parse.quote(league_id,safe='')}/events?limit=1000"
        root=_json(url,timeout=8)
        items=root.get("items") if isinstance(root,dict) else root
        for item in items or []:
            event=item if isinstance(item,dict) else {}
            normalized=_event_from_espn(event,league)
            if normalized and normalized["providerEventId"] not in seen:
                seen.add(normalized["providerEventId"]); out.append(normalized)
    except Exception:
        pass
    return True,out

def _cricket_header(league):
    wanted={"IPL":{"ipl","indianpremierleague"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20"}}
    try:
        root=_json("https://site.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket&region=in&tz=Asia/Calcutta",timeout=8)
        series_list=(((root.get("sports") or [{}])[0]).get("leagues") or []) if isinstance(root,dict) else []
        out=[]
        for series in series_list:
            names={_norm(series.get("name")),_norm(series.get("slug")),_norm(series.get("abbreviation")),_norm(series.get("shortName")),_norm(series.get("shortAlternateName"))}
            if not any(any(alias in name for alias in wanted.get(league,set())) for name in names):
                continue
            for event in series.get("events") or []:
                normalized=_event_from_espn(event,league,"espn-cricket-header")
                if normalized: out.append(normalized)
        return True,out
    except Exception:
        return False,[]

def _cricinfo_current(league):
    try:
        root=_json("https://hs-consumer-api.espncricinfo.com/v1/pages/matches/current?lang=en&latest=true",timeout=8)
        rows=root.get("matches") or root.get("content") or root.get("results") or []
        out=[]
        def walk(value):
            if isinstance(value,dict):
                if value.get("objectId") or value.get("matchId") or value.get("id"):
                    yield value
                for child in value.values():
                    yield from walk(child)
            elif isinstance(value,list):
                for child in value: yield from walk(child)
        aliases={"IPL":{"ipl","indianpremierleague"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20"}}
        for match in walk(rows):
            text=_norm(match.get("seriesName") or match.get("series",{}).get("name") or match.get("name") or "")
            if not any(alias in text for alias in aliases.get(league,set())): continue
            teams=match.get("teams") or []
            names=[]
            for team in teams[:2]:
                if isinstance(team,dict): names.append(str(team.get("name") or team.get("teamName") or team.get("shortName") or "").strip())
            start=match.get("startTime") or match.get("startDate") or match.get("date")
            if not start: continue
            title=" @ ".join(reversed(names)) if len(names)==2 else str(match.get("name") or league)
            out.append({"league":league,"title":title,"start":_iso(start),"tag":"LIVE" if _norm(match.get("status") or "").find("live")>=0 else "UPCOMING","icon":"🏏","source":"espncricinfo","providerEventId":f"espncricinfo:{match.get('objectId') or match.get('matchId') or match.get('id') or start}"})
        return True,out
    except Exception:
        return False,[]

def sportscore(league,icon):
    if league in {"IPL","ICC T20"}:
        ok,rows=_cricket_header(league)
        if ok and rows:return True,rows,""
        ok,rows=_cricket_core(league)
        if ok and rows:return True,rows,""
        ok,rows=_cricinfo_current(league)
        if ok and rows:return True,rows,""
        return True,[],""
    return _legacy.sportscore(league,icon)

def fetch(provider,league,icon):
    if provider=="sportscore":
        return sportscore(league,icon)
    return _legacy.fetch(provider,league,icon)
