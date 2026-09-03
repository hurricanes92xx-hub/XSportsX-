#!/usr/bin/env python3
"""Optional expanded provider adapters.

Paid providers are opt-in via GitHub Actions secrets. They are deliberately
isolated from the core engine so missing credentials never break refreshes.
"""
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "XSportsX-Provider/1.0", "Accept": "application/json"}


def _get(url: str, headers=None, timeout=10):
    req = urllib.request.Request(url, headers={**HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _iso(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(value)


def _team(obj, side):
    value = obj.get(side) or obj.get(f"{side}Team") or obj.get(f"{side}_team") or {}
    if isinstance(value, dict):
        return value.get("shortDisplayName") or value.get("displayName") or value.get("name") or value.get("abbreviation") or ""
    return str(value or "")


def _generic_events(root, league, source, icon):
    if isinstance(root, dict):
        raw = root.get("events") or root.get("games") or root.get("fixtures") or root.get("data") or []
    else:
        raw = root
    if not isinstance(raw, list):
        return []
    out=[]
    for item in raw:
        if not isinstance(item, dict):
            continue
        home=_team(item,"home"); away=_team(item,"away")
        title=item.get("name") or item.get("shortName") or (f"{away} @ {home}" if home and away else "")
        start=item.get("startDate") or item.get("startTime") or item.get("date") or item.get("starting_at") or item.get("start")
        if not title or not start:
            continue
        status=str(item.get("status") or item.get("state") or "").lower()
        tag="LIVE" if status in {"live","in","in_progress","inprogress"} else ("FINAL" if status in {"final","post","completed"} else "UPCOMING")
        e={"league":league,"title":title,"start":_iso(start),"tag":tag,"icon":icon,"source":source}
        if home:e["home"]=home
        if away:e["away"]=away
        pid=item.get("id") or item.get("gameId") or item.get("fixture_id")
        if pid:e["providerEventId"]=f"{source}:{pid}"
        out.append(e)
    return out


def _template(provider, league):
    key={"sportradar":"SPORTRADAR_ENDPOINT_TEMPLATE","sportsdataio":"SPORTSDATAIO_ENDPOINT_TEMPLATE","sportmonks":"SPORTMONKS_ENDPOINT_TEMPLATE"}[provider]
    template=os.getenv(key,"").strip()
    if not template:return ""
    return template.format(league=urllib.parse.quote(league), league_raw=league)


def fetch(provider, league, icon):
    if provider in {"sportradar","sportsdataio","sportmonks"}:
        key=os.getenv({"sportradar":"SPORTRADAR_API_KEY","sportsdataio":"SPORTSDATAIO_API_KEY","sportmonks":"SPORTMONKS_API_TOKEN"}[provider],"").strip()
        url=_template(provider,league)
        if not key or not url:return False,[],"not configured"
        header={"x-api-key":key} if provider=="sportradar" else ({"Ocp-Apim-Subscription-Key":key} if provider=="sportsdataio" else {})
        if provider=="sportmonks":
            sep="&" if "?" in url else "?"; url=f"{url}{sep}api_token={urllib.parse.quote(key)}"
        try:return True,_generic_events(_get(url,header),league,provider,icon),""
        except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

    if provider=="cfbd":
        key=os.getenv("CFBD_API_KEY","").strip()
        if not key:return False,[],"not configured"
        year=datetime.now(timezone.utc).year
        url=f"https://api.collegefootballdata.com/games?year={year}&seasonType=regular&division=fbs"
        try:return True,_generic_events(_get(url,{"Authorization":f"Bearer {key}"}),"NCAA FB",provider,icon),""
        except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

    if provider=="mlb-official":
        url="https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={}&endDate={}&hydrate=team".format((datetime.now(timezone.utc)-timedelta(days=1)).date(),(datetime.now(timezone.utc)+timedelta(days=30)).date())
        try:
            root=_get(url); out=[]
            for date in root.get("dates",[]):
                for g in date.get("games",[]):
                    home=((g.get("teams") or {}).get("home") or {}).get("team") or {}; away=((g.get("teams") or {}).get("away") or {}).get("team") or {}
                    h=home.get("name",""); a=away.get("name",""); start=_iso(g.get("gameDate")); state=str((((g.get("status") or {}).get("abstractGameState")) or "")).lower()
                    tag="LIVE" if state=="live" else ("FINAL" if state in {"final","completed"} else "UPCOMING")
                    if h and a and start:out.append({"league":"MLB","title":f"{a} @ {h}","start":start,"tag":tag,"icon":icon,"source":provider,"home":h,"away":a,"providerEventId":f"mlb:{g.get('gamePk')}"})
            return bool(out),out,""
        except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

    if provider=="nhl-official":
        url="https://api-web.nhle.com/v1/schedule/{}".format(datetime.now(timezone.utc).date())
        try:
            root=_get(url); out=[]
            for day in root.get("gameWeek",[]):
                for g in day.get("games",[]):
                    h=(g.get("homeTeam") or {}).get("placeName",{}).get("default",""); a=(g.get("awayTeam") or {}).get("placeName",{}).get("default","")
                    start=_iso(g.get("startTimeUTC")); state=str(g.get("gameState") or "").lower(); tag="LIVE" if state in {"live","critical"} else ("FINAL" if state in {"final","off"} else "UPCOMING")
                    if h and a and start:out.append({"league":"NHL","title":f"{a} @ {h}","start":start,"tag":tag,"icon":icon,"source":provider,"home":h,"away":a,"providerEventId":f"nhl:{g.get('id')}"})
            return bool(out),out,""
        except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

    return False,[],"unknown provider"
