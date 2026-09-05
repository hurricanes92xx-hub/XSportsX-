#!/usr/bin/env python3
"""Free/keyless shadow providers for leagues whose dedicated feeds are fragile.

These are metadata/live-state fallbacks only. They never replace a stronger
canonical provider unless the normal matrix promotion logic selects them.
"""
from __future__ import annotations
import json, urllib.request
from datetime import datetime, timezone, timedelta

HEADERS={"User-Agent":"XSportsX-Shadow/1.0","Accept":"application/json"}

def _get(url, timeout=10):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","ignore"))

def _iso(v):
    if not v:return ""
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except Exception:return str(v)

def _events(root, league, icon, source):
    raw=root.get("events") if isinstance(root,dict) else []
    out=[]
    for event in raw or []:
        comp=(event.get("competitions") or [{}])[0]
        teams=comp.get("competitors") or []
        home=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="home"),"")
        away=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in teams if x.get("homeAway")=="away"),"")
        start=_iso(event.get("date") or event.get("startDate"))
        if not start:continue
        state=str(((comp.get("status") or {}).get("type") or {}).get("state") or "pre").lower()
        tag="LIVE" if state=="in" else "FINAL" if state=="post" else "UPCOMING"
        out.append({"league":league,"title":f"{away} @ {home}" if home and away else str(event.get("name") or event.get("shortName") or league),"start":start,"tag":tag,"icon":icon,"source":source,"home":home,"away":away,"providerEventId":f"{source}:{event.get('id') or start}","status":"LIVE" if tag=="LIVE" else tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre"})
    return out

def espn(league, sport, slug, icon):
    now=datetime.now(timezone.utc).date()
    days=[now-timedelta(days=1),now,now+timedelta(days=1)]
    out=[]; errors=[]
    for day in days:
        url=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={day:%Y%m%d}&limit=1000"
        try:out.extend(_events(_get(url),league,icon,"espn-shadow"))
        except Exception as exc:errors.append(str(exc))
    return True,out,"; ".join(errors)[:300] if errors and not out else ""

def cricket(league, icon):
    try:
        root=_get("https://site.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket&region=in&tz=Asia/Calcutta")
        wanted={"IPL":{"ipl","indianpremierleague"},"ICC T20":{"icct20","t20worldcup","internationalcrickett20"}}
        def norm(v):return "".join(c.lower() for c in str(v or "") if c.isalnum())
        out=[]
        sports=root.get("sports") or [] if isinstance(root,dict) else []
        for sportrow in sports:
            for series in sportrow.get("leagues") or []:
                names={norm(series.get("name")),norm(series.get("slug")),norm(series.get("abbreviation")),norm(series.get("shortName"))}
                if not any(any(a in n for a in wanted.get(league,set())) for n in names):continue
                for event in series.get("events") or []:
                    comp=(event.get("competitions") or [{}])[0]; teams=comp.get("competitors") or []
                    home=next((x.get("team",{}).get("displayName") or x.get("team",{}).get("shortDisplayName") for x in teams if x.get("homeAway")=="home"),"")
                    away=next((x.get("team",{}).get("displayName") or x.get("team",{}).get("shortDisplayName") for x in teams if x.get("homeAway")=="away"),"")
                    start=_iso(event.get("date") or event.get("startDate"))
                    if not start:continue
                    state=str(((comp.get("status") or {}).get("type") or {}).get("state") or "pre").lower(); tag="LIVE" if state=="in" else "FINAL" if state=="post" else "UPCOMING"
                    out.append({"league":league,"title":f"{away} @ {home}" if home and away else str(event.get("name") or series.get("name") or league),"start":start,"tag":tag,"icon":icon,"source":"espn-cricket-shadow","home":home,"away":away,"providerEventId":f"espn-cricket:{event.get('id') or start}","status":"LIVE" if tag=="LIVE" else tag,"state":"in" if tag=="LIVE" else "post" if tag=="FINAL" else "pre"})
        return True,out,""
    except Exception as exc:return False,[],f"{type(exc).__name__}: {exc}"

def fetch(provider,league,icon):
    if provider=="espn-racing" and league=="NASCAR Truck":return espn(league,"racing","nascar-truck",icon)
    if provider=="espn-xgames":
        # ESPN has exposed X Games through its public action-sports feed in
        # different forms over time; try the current scoreboard first and a
        # legacy action-sports path second.
        for sport,slug in (("action-sports","x-games"),("action-sports","xgames"),("extreme-sports","x-games")):
            try:
                ok,rows,err=espn(league,sport,slug,icon)
                if rows:return ok,rows,err
            except Exception:pass
        return False,[],"X Games public ESPN shadow unavailable"
    if provider=="espn-cricket" and league in {"IPL","ICC T20"}:return cricket(league,icon)
    return False,[],"unsupported shadow provider"
