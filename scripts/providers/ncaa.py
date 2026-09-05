#!/usr/bin/env python3
"""NCAA schedule provider with official + ESPN fallback coverage and 428 circuit breaker."""
import json,re,time,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
BASE="https://ncaa-api.henrygd.me"; OFFICIAL_BASE="https://data.ncaa.com/casablanca/scoreboard"; HEADERS={"User-Agent":"XSportsX-Schedule/7.0","Accept":"application/json"}; ESPN_HEADERS=HEADERS; NCAA_TZ=ZoneInfo("America/New_York"); MAX_WORKERS=3; RETRIES=2
PRIMARY_DISABLED={"NCAA Softball","NCAA Women's Field Hockey","NCAA Beach Volleyball"}
PRIMARY_BLOCKED=False
NCAA_LEAGUES=[("NCAA FB","football","fbs","🏈"),("NCAA BB","basketball-men","d1","🏀"),("NCAA WBB","basketball-women","d1","🏀"),("NCAA Baseball","baseball","d1","⚾"),("NCAA Softball","softball","d1","🥎"),("NCAA Men's Hockey","icehockey-men","d1","🏒"),("NCAA Women's Hockey","icehockey-women","d1","🏒"),("NCAA Men's Soccer","soccer-men","d1","⚽"),("NCAA Women's Soccer","soccer-women","d1","⚽"),("NCAA Men's Lacrosse","lacrosse-men","d1","🥍"),("NCAA Women's Lacrosse","lacrosse-women","d1","🥍"),("NCAA Men's Volleyball","volleyball-men","d1","🏐"),("NCAA Women's Volleyball","volleyball-women","d1","🏐"),("NCAA Men's Water Polo","waterpolo-men","d1","🤽"),("NCAA Women's Water Polo","waterpolo-women","d1","🤽"),("NCAA Women's Field Hockey","fieldhockey-women","d1","🏑"),("NCAA Beach Volleyball","beach-volleyball","d1","🏐")]
ESPN_FALLBACK={"NCAA FB":("football","college-football"),"NCAA BB":("basketball","mens-college-basketball"),"NCAA WBB":("basketball","womens-college-basketball"),"NCAA Baseball":("baseball","college-baseball"),"NCAA Softball":("softball","college-softball"),"NCAA Men's Hockey":("hockey","mens-college-hockey"),"NCAA Women's Hockey":("hockey","womens-college-hockey"),"NCAA Men's Soccer":("soccer","usa.ncaa.m.1"),"NCAA Women's Soccer":("soccer","usa.ncaa.w.1"),"NCAA Men's Lacrosse":("lacrosse","mens-college-lacrosse"),"NCAA Women's Lacrosse":("lacrosse","womens-college-lacrosse"),"NCAA Men's Volleyball":("volleyball","mens-college-volleyball"),"NCAA Women's Volleyball":("volleyball","womens-college-volleyball"),"NCAA Men's Water Polo":("water-polo","mens-college-water-polo"),"NCAA Women's Water Polo":("water-polo","womens-college-water-polo"),"NCAA Women's Field Hockey":("field-hockey","womens-college-field-hockey"),"NCAA Beach Volleyball":("beach-volleyball","ncaa-beach-volleyball")}
def _get(url,headers=HEADERS,timeout=15):
 global PRIMARY_BLOCKED
 last=None
 for attempt in range(RETRIES):
  try:
   req=urllib.request.Request(url,headers=headers)
   with urllib.request.urlopen(req,timeout=timeout) as response:return json.loads(response.read())
  except urllib.error.HTTPError as exc:
   last=exc
   if exc.code==428 and url.startswith(BASE):
    PRIMARY_BLOCKED=True
    raise
   if exc.code not in {429,500,502,503,504}:break
   time.sleep(1.5*(attempt+1))
  except (urllib.error.URLError,TimeoutError,json.JSONDecodeError) as exc:last=exc;time.sleep(.75*(attempt+1))
 raise last
def _parse_iso(value):
 if not value:return None
 try:return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
 except:return None
def _walk_games(value):
 if isinstance(value,dict):
  if (value.get("startDate") or value.get("gameDate") or value.get("date")) and (value.get("away") or value.get("home") or value.get("teams") or value.get("contestId") or value.get("gameID")):yield value
  for child in value.values():yield from _walk_games(child)
 elif isinstance(value,list):
  for child in value:yield from _walk_games(child)
def _team_name(team):
 if not isinstance(team,dict):return ""
 names=team.get("names") or {};return str(names.get("short") or names.get("full") or names.get("seo") or team.get("name") or "").strip()
def _parse_time(game):
 date=str(game.get("startDate") or game.get("gameDate") or "").strip(); raw=str(game.get("startTime") or "").strip().upper().replace(" ET","")
 if not date:return None
 if not raw:return _parse_iso(game.get("date")) and _parse_iso(game.get("date")).isoformat().replace("+00:00","Z")
 for fmt in ("%Y-%m-%d %I:%M%p","%Y-%m-%d %H:%M","%Y-%m-%dT%I:%M%p","%Y-%m-%dT%H:%M"):
  try:
   t=f"{date} {raw}" if "T" not in date else f"{date}T{raw}";return datetime.strptime(t,fmt).replace(tzinfo=NCAA_TZ).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
  except ValueError:continue
 return None
def _normalize(game,league,icon):
 away,home=_team_name(game.get("away")),_team_name(game.get("home"));teams=game.get("teams") or []
 if not away and isinstance(teams,list) and teams:away=_team_name(teams[0])
 if not home and isinstance(teams,list) and len(teams)>1:home=_team_name(teams[1])
 title=f"{away} @ {home}" if away and home else str(game.get("title") or game.get("contestName") or league);state=str(game.get("gameState") or game.get("status") or "").lower()
 if isinstance(game.get("status"),dict):
  s=game["status"];state=str(s.get("state") or s.get("name") or s.get("displayClock") or "").lower()
 status_text=json.dumps(game.get("status"),ensure_ascii=False).lower() if isinstance(game.get("status"),(dict,list)) else state;live_clock=bool(re.search(r"\bq[1-4]\b|\b[0-9]{1,2}:[0-9]{2}\b|halftime|in progress|in-progress|inprogress|live|set [1-7]",status_text+" "+state));final_state=bool(re.search(r"final|complete|completed|closed",status_text+" "+state));tag="FINAL" if final_state else "LIVE" if live_clock else "UPCOMING";pid=game.get("contestId") or game.get("gameID") or game.get("gameId") or ""
 event={"league":league,"title":title,"tag":tag,"icon":icon,"source":"ncaa"}
 if start:=_parse_time(game):event["start"]=start;event["startUtc"]=start
 if away:event["away"]=away
 if home:event["home"]=home
 if pid:event["providerEventId"]=f"ncaa:{pid}"
 event.update({"status":tag,"state":{"LIVE":"in","FINAL":"post","UPCOMING":"pre"}[tag]});return event
def _normalize_espn(game,league,icon):
 dt=_parse_iso(game.get("date"))
 if not dt:return None
 comp=(game.get("competitions") or [{}])[0];competitors=comp.get("competitors") or []
 home=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in competitors if x.get("homeAway")=="home"),"");away=next((x.get("team",{}).get("shortDisplayName") or x.get("team",{}).get("displayName") for x in competitors if x.get("homeAway")=="away"),"");state=str(((comp.get("status") or {}).get("type") or {}).get("state") or "").lower();tag="LIVE" if state=="in" else "FINAL" if state=="post" else "UPCOMING";event={"league":league,"title":f"{away} @ {home}" if away and home else str(game.get("name") or game.get("shortName") or league),"start":dt.isoformat().replace("+00:00","Z"),"startUtc":dt.isoformat().replace("+00:00","Z"),"tag":tag,"icon":icon,"source":"espn-ncaa"}
 if away:event["away"]=away
 if home:event["home"]=home
 if game.get("id"):event["providerEventId"]=f"espn:{game['id']}"
 event.update({"status":tag,"state":{"LIVE":"in","FINAL":"post","UPCOMING":"pre"}[tag]});return event
def _fetch_scoreboard_day(sport,division,day):
 if PRIMARY_BLOCKED:return None
 url=f"{BASE}/scoreboard/football/{division}" if sport=="football" else f"{BASE}/scoreboard/{sport}/{division}/{day:%Y/%m/%d}"
 try:return _get(url)
 except urllib.error.HTTPError as exc:
  if exc.code==428:print(f"DISABLE NCAA legacy endpoint after HTTP 428: {sport}/{division}")
  return None
 except Exception as exc:print(f"ERROR NCAA scoreboard {sport}/{division} {day}: {exc}");return None
def _fetch_official_day(sport,division,day):
 # Official NCAA Casablanca scoreboard JSON. Used before third-party mirrors.
 url=f"{OFFICIAL_BASE}/{sport}/{division}/{day:%Y/%m/%d}/scoreboard.json"
 try:return _get(url,HEADERS,12)
 except Exception as exc:print(f"ERROR NCAA official scoreboard {sport}/{division} {day}: {exc}");return None
def _fetch_espn_day(league,day):
 mapping=ESPN_FALLBACK.get(league)
 if not mapping:return []
 sport,slug=mapping;root=None
 for url in (f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={day:%Y%m%d}&limit=1000",f"https://site.web.api.espn.com/apis/site/v2/sports/{sport}/{slug}/scoreboard?dates={day:%Y%m%d}&limit=1000"):
  try:root=_get(url,ESPN_HEADERS,12);break
  except Exception as exc:print(f"ERROR ESPN NCAA secondary {league} {day}: {exc}")
 if not root:return []
 icon=next(x[3] for x in NCAA_LEAGUES if x[0]==league);return [event for game in root.get("events") or [] if (event:=_normalize_espn(game,league,icon))]
def _fetch_espn_days(league,days):
 out=[]
 with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,max(1,len(days)))) as pool:
  for future in as_completed([pool.submit(_fetch_espn_day,league,day) for day in days]):out.extend(future.result())
 return out
def _fetch_primary_days(sport,division,days):
 # Official NCAA is the preferred primary. Legacy mirror is only tried once and
 # is globally circuit-broken after its first 428 to prevent request storms.
 roots=[]
 with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,max(1,len(days)))) as pool:
  for f in as_completed([pool.submit(_fetch_official_day,sport,division,d) for d in days]):
   r=f.result()
   if r:roots.append(r)
 if roots:return roots
 if PRIMARY_BLOCKED:return []
 with ThreadPoolExecutor(max_workers=min(MAX_WORKERS,max(1,len(days)))) as pool:
  return [f.result() for f in as_completed([pool.submit(_fetch_scoreboard_day,sport,division,d) for d in days])]
def _in_window(event,now,cutoff):
 dt=_parse_iso(event.get("start"));return bool(dt and now-timedelta(hours=12)<=dt<=cutoff)
def fetch_league(league,sport,division,icon,horizon_days=30):
 now=datetime.now(timezone.utc);cutoff=now+timedelta(days=min(horizon_days,7));days=[now.date()+timedelta(days=i) for i in range((cutoff.date()-now.date()).days+1)];primary=[]
 if league not in PRIMARY_DISABLED:
  for root in _fetch_primary_days(sport,division,days):
   if root:
    for game in _walk_games(root):
     event=_normalize(game,league,icon)
     if event and (event.get("tag")=="LIVE" or _in_window(event,now,cutoff)):primary.append(event)
 else:print(f"SKIP NCAA legacy primary {league}: using official NCAA + ESPN secondary")
 secondary=[e for e in _fetch_espn_days(league,days) if _in_window(e,now,cutoff)];out=[];seen=set()
 for event in primary+secondary:
  key=(event.get("providerEventId") or "",event.get("league"),event.get("away"),event.get("home"),event.get("start"))
  if key in seen:continue
  seen.add(key);out.append(event)
 if secondary and not primary:print(f"REPAIRED NCAA {league} via ESPN secondary: {len(secondary)} events")
 elif secondary:print(f"NCAA {league}: primary={len(primary)} secondary={len(secondary)} union={len(out)}")
 return out
