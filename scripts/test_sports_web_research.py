#!/usr/bin/env python3
import sports_web_research as r

rows=r.research_live({"title":"Synthetic Test Match","league":"Test League","startUtc":"2026-09-04T19:00:00Z"},limit=2)
assert isinstance(rows,list)
assert all(0 <= float(x.get("score",0)) <= 1 for x in rows)
rows=r.research_schedule("Test League",{"title":"Synthetic Test Match","startUtc":"2026-09-04T19:00:00Z"},limit=2)
assert isinstance(rows,list)
assert all(x.get("url") for x in rows)
print("SPORTS_WEB_RESEARCH: PASS")
