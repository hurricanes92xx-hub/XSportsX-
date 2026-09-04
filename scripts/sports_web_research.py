#!/usr/bin/env python3
"""Bounded Google-backed research for schedule and live gaps.

Search is evidence discovery, not a canonical source. Results are filtered and
ranked; downstream matching still decides whether an event/source is usable.
"""
from __future__ import annotations
import html
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
import provider_discovery as discovery

UA = "XSportsX-WebResearch/1.0"
OFFICIAL_HINTS = (".gov", ".edu", "official", "league", "ncaa", "nfl", "nba", "nhl", "mlb", "fifa", "uefa", "fivb", "pga", "lpga", "ufc", "wwe", "nascar", "formula1", "indycar", "motogp")


def _google_results(query: str, limit: int = 10):
    # Prefer Google's programmable search when configured; otherwise use the
    # existing no-key Google News RSS discovery path.
    rows = discovery._google_cse(query)
    if rows:
        return rows[:limit]
    return discovery._google_news(query)[:limit]


def _score(url: str, title: str, snippet: str, query_kind: str) -> float:
    text = f"{url} {title} {snippet}".lower()
    score = 0.25
    if any(h in text for h in OFFICIAL_HINTS): score += 0.30
    if query_kind == "live":
        if any(x in text for x in ("live", "watch", "stream", "broadcast", "coverage")): score += 0.25
        if "youtube.com" in url.lower() or "youtu.be" in url.lower(): score += 0.12
    else:
        if any(x in text for x in ("schedule", "fixture", "fixtures", "calendar", "match")): score += 0.25
    return round(min(0.98, score), 3)


def _dedupe(rows):
    seen=set(); out=[]
    for row in rows:
        url=str(row.get("url") or "").strip()
        if not url or url in seen: continue
        seen.add(url); out.append(row)
    return out


def research_schedule(league: str, event: dict | None = None, limit: int = 12):
    title = str((event or {}).get("title") or "").strip()
    date = str((event or {}).get("startUtc") or (event or {}).get("start") or "")[:10]
    queries = [f'"{league}" official schedule', f'"{league}" fixtures schedule {datetime.now(timezone.utc).year}']
    if title: queries.insert(0, f'"{title}" "{date}" schedule')
    rows=[]
    for q in queries[:3]:
        for url, t, s in _google_results(q, 8):
            rows.append({"url":url,"title":html.unescape(t)[:240],"snippet":html.unescape(s)[:500],"score":_score(url,t,s,"schedule"),"query":q})
    return sorted(_dedupe(rows), key=lambda x:x["score"], reverse=True)[:limit]


def research_live(event: dict, limit: int = 12):
    title=str(event.get("title") or "").strip(); league=str(event.get("league") or "").strip(); date=str(event.get("startUtc") or event.get("start") or "")[:10]
    if not title: return []
    queries=[f'"{title}" "{date}" live', f'"{title}" {league} watch live', f'"{title}" official broadcast live']
    rows=[]
    for q in queries:
        for url,t,s in _google_results(q, 8):
            rows.append({"url":url,"title":html.unescape(t)[:240],"snippet":html.unescape(s)[:500],"score":_score(url,t,s,"live"),"query":q})
    return sorted(_dedupe(rows), key=lambda x:x["score"], reverse=True)[:limit]


def main():
    import argparse, json
    p=argparse.ArgumentParser(); p.add_argument("kind",choices=("schedule","live")); p.add_argument("league"); p.add_argument("title",nargs="?",default=""); p.add_argument("start",nargs="?",default="")
    a=p.parse_args(); event={"title":a.title,"league":a.league,"startUtc":a.start}
    rows=research_schedule(a.league,event) if a.kind=="schedule" else research_live(event)
    print(json.dumps({"schema":1,"kind":a.kind,"results":rows},indent=2))

if __name__=='__main__': main()
