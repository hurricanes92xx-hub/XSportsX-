#!/usr/bin/env python3
"""Bounded sports web research with authoritative-site prioritization.

The web is evidence discovery, not blindly canonical data. Official league,
team/federation sites and ESPN are explicitly prioritized, then broader search.
"""
from __future__ import annotations
import html, urllib.parse
from datetime import datetime, timezone
import provider_discovery as discovery

UA = "XSportsX-WebResearch/1.1"
OFFICIAL_DOMAINS = {
    "nfl":["nfl.com"],"nba":["nba.com"],"wnba":["wnba.com"],"mlb":["mlb.com"],"nhl":["nhl.com"],"mls":["mlssoccer.com"],
    "ncaa":["ncaa.com"],"epl":["premierleague.com"],"uefa":["uefa.com"],"ucl":["uefa.com"],"uel":["uefa.com"],
    "fifa":["fifa.com"],"fivb":["fivb.com"],"pga":["pgatour.com"],"lpga":["lpga.com"],"ufc":["ufc.com"],
    "wwe":["wwe.com"],"nascar":["nascar.com"],"formula 1":["formula1.com"],"f1":["formula1.com"],
    "indycar":["indycar.com"],"motogp":["motogp.com"],"pll":["premierlacrosseleague.com"],"nll":["nll.com"],
    "atp":["atptour.com"],"wta":["wtatennis.com"],"icc":["icc-cricket.com"],"rugby":["world.rugby"],
    "wrc":["wrc.com"],"wec":["fiawec.com"],"imsa":["imsa.com"],"formula e":["fiaformulae.com"],"cfl":["cfl.ca"],
    "nwsl":["nwslsoccer.com"],"nwsL":["nwslsoccer.com"]
}
ESPN_DOMAIN="espn.com"

def _domain_for_league(league):
    low=str(league).lower().strip(); out=[]
    for key, domains in OFFICIAL_DOMAINS.items():
        if key.lower() in low or low in key.lower(): out.extend(domains)
    return list(dict.fromkeys(out))

def _google_results(query, limit=10):
    rows=discovery._google_cse(query)
    return (rows or discovery._google_news(query))[:limit]

def _score(url,title,snippet,kind,official):
    text=f"{url} {title} {snippet}".lower(); host=(urllib.parse.urlparse(url).hostname or "").lower(); score=.20
    if any(host==d or host.endswith("."+d) for d in official): score+=.50
    if host==ESPN_DOMAIN or host.endswith("."+ESPN_DOMAIN): score+=.32
    if any(x in text for x in ("official","league","ncaa","fifa","uefa","fivb")): score+=.10
    if kind=="live":
        if any(x in text for x in ("live","watch","broadcast","coverage")): score+=.22
        if "youtube.com" in host or "youtu.be" in host: score+=.08
    elif any(x in text for x in ("schedule","fixture","fixtures","calendar","match")): score+=.22
    return round(min(.99,score),3)

def _dedupe(rows):
    seen=set(); out=[]
    for row in rows:
        u=str(row.get("url") or "").strip()
        if u and u not in seen: seen.add(u); out.append(row)
    return out

def _research(league,event,kind,limit):
    title=str((event or {}).get("title") or "").strip(); date=str((event or {}).get("startUtc") or (event or {}).get("start") or "")[:10]
    official=_domain_for_league(league)
    if kind=="schedule":
        queries=[f'"{league}" official schedule',f'"{league}" schedule {datetime.now(timezone.utc).year}',f'"{league}" ESPN schedule']
        if title: queries.insert(0,f'"{title}" "{date}" schedule')
    else:
        queries=[f'"{title}" "{date}" live',f'"{title}" {league} ESPN live',f'"{title}" official broadcast live',f'"{title}" watch live']
    for d in official[:2]: queries.append(f'"{league}" {"schedule" if kind=="schedule" else "live"} site:{d}')
    queries.append(f'"{league}" {"schedule" if kind=="schedule" else "live"} site:{ESPN_DOMAIN}')
    rows=[]
    for q in queries[:7]:
        for url,t,s in _google_results(q,8):
            host=(urllib.parse.urlparse(url).hostname or "").lower()
            is_official=any(host==d or host.endswith("."+d) for d in official)
            is_espn=host==ESPN_DOMAIN or host.endswith("."+ESPN_DOMAIN)
            rows.append({"url":url,"title":html.unescape(t)[:240],"snippet":html.unescape(s)[:500],"score":_score(url,t,s,kind,official),"query":q,"authority":"official" if is_official else "espn" if is_espn else "discovered"})
    return sorted(_dedupe(rows),key=lambda x:x["score"],reverse=True)[:limit]

def research_schedule(league,event=None,limit=12): return _research(league,event,"schedule",limit)
def research_live(event,limit=12): return _research(str(event.get("league") or ""),event,"live",limit)

def main():
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument("kind",choices=("schedule","live"));p.add_argument("league");p.add_argument("title",nargs="?",default="");p.add_argument("start",nargs="?",default="")
    a=p.parse_args();e={"title":a.title,"league":a.league,"startUtc":a.start};r=research_schedule(a.league,e) if a.kind=="schedule" else research_live(e);print(json.dumps({"schema":2,"kind":a.kind,"results":r},indent=2))
if __name__=='__main__': main()
