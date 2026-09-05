#!/usr/bin/env python3
"""Dedicated official live adapters for FIVB and NASCAR."""
from __future__ import annotations
import json, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEED = ROOT / "data" / "schedule_feed.json"
UA = "XSportsX-OfficialLiveAdapters/1.4"
FIVB_URL = "https://www.fivb.org/Vis2009/XmlRequest.asmx"


def _get(url, timeout=10, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _post_xml(xml, timeout=12):
    body = urllib.parse.urlencode({"Request": xml}).encode()
    req = urllib.request.Request(FIVB_URL, data=body, headers={"User-Agent": UA, "Accept": "application/xml, text/xml, */*", "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _iso(v):
    if not v: return ""
    try: return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception: return ""


def _norm(v): return "".join(c.lower() for c in str(v or "") if c.isalnum())

LIVE_STATUSES = {f"inset{i}" for i in range(1, 8)}

def _is_live(v): return _norm(v) in LIVE_STATUSES


def _field(el, *names):
    wanted = {n.lower() for n in names}
    for k, v in el.attrib.items():
        if k.lower() in wanted and str(v).strip(): return str(v).strip()
    for child in el:
        if child.tag.split("}")[-1].lower() in wanted and child.text and child.text.strip(): return child.text.strip()
    return ""


def _desc_field(el, *names):
    value = _field(el, *names)
    if value: return value
    wanted = {n.lower() for n in names}
    for node in el.iter():
        if node is el: continue
        if node.tag.split("}")[-1].lower() in wanted and node.text and node.text.strip(): return node.text.strip()
    return ""


def _fivb_records(root):
    """Parse the actual VIS list shape without requiring TeamName fields on the row.

    VIS returns VolleyballMatch records (the docs call them VolleyMatch data) and
    team/tournament relations can be nested. We therefore identify records by No,
    then search the record subtree for status, team names and tournament metadata.
    """
    records = []
    for el in root.iter():
        tag = el.tag.split("}")[-1].lower()
        if tag not in {"volleyballmatch", "volleymatch", "match"}: continue
        no = _desc_field(el, "No", "NoMatch", "NoVolleyMatch")
        if no and str(no).isdigit(): records.append(el)
    return records


def _fivb_live_request(no):
    errors = []
    # GetVolleyLive is documented with No=<match number>, Options=128 and Version=0.
    # Do not retry alternate parameter spellings: once the match list identifies a
    # live match, one correctly formed verification request is enough.
    request = f'<Request Type="GetVolleyLive" No="{int(no)}" Options="128" Version="0" />'
    try:
        raw = _post_xml(request)
        root = ET.fromstring(raw)
        tags = {n.tag.split("}")[-1].lower() for n in root.iter()}
        if "volleylive" in tags or root.tag.split("}")[-1].lower() == "volleylive":
            return True, "volleylive"
        if "nochanges" in tags:
            return True, "nochanges"
        for node in root.iter():
            tag = node.tag.split("}")[-1].lower()
            if tag in {"error", "badparameter", "nodata", "parametermissing", "accessdenied"}:
                errors.append(tag)
    except urllib.error.HTTPError as exc:
        errors.append(f"http:{exc.code}")
    except Exception as exc:
        errors.append(type(exc).__name__)
    return False, ";".join(errors) or "no-live-payload"


def _fivb():
    result = []
    diagnostics = {"status":"ok", "listRecords":0, "candidates":0, "liveVerified":0, "liveRejected":0, "errors":[], "verification":{}}
    request = '<Request Type="GetVolleyMatchList" Fields="No DateTimeUtc BeginDateTimeUtc TeamNameA TeamNameB Status Gender TournamentName"><Filter ForLiveScore="true" /></Request>'
    try:
        raw = _post_xml(request)
        root = ET.fromstring(raw)
    except Exception as exc:
        diagnostics["status"] = "unavailable"; diagnostics["errors"].append(f"list:{type(exc).__name__}"); return result, diagnostics

    records = _fivb_records(root)
    diagnostics["listRecords"] = len(records)
    for el in records:
        no = _desc_field(el, "No", "NoMatch", "NoVolleyMatch")
        status = _desc_field(el, "Status", "StatusName", "MatchStatus")
        # The list response itself is the authority for whether a match is live.
        # Only InSet1..InSet7 are eligible for GetVolleyLive verification.
        if not _is_live(status): continue
        diagnostics["candidates"] += 1
        home = _desc_field(el, "TeamNameA", "TeamAName", "NameA", "TeamA")
        away = _desc_field(el, "TeamNameB", "TeamBName", "NameB", "TeamB")
        start = _iso(_desc_field(el, "DateTimeUtc", "BeginDateTimeUtc", "DateUtc"))
        gender = _norm(_desc_field(el, "Gender", "TournamentGender"))
        tournament = _desc_field(el, "TournamentName", "Name")
        league = "FIVB Women" if gender in {"w","women","female","f"} or "women" in _norm(tournament) or "feminin" in _norm(tournament) else "FIVB Men"
        confirmed, why = _fivb_live_request(no)
        diagnostics["verification"][str(no)] = why
        if not confirmed:
            diagnostics["liveRejected"] += 1; continue
        result.append({"league":league,"title":f"{away} @ {home}" if away and home else f"FIVB Match {no}","start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","home":home,"away":away,"source":"fivb-vis-official","providerEventId":f"fivb:{no}","liveEvidenceSource":"fivb-vis"})
        diagnostics["liveVerified"] += 1
    return result, diagnostics


def _nascar():
    result=[]; diagnostics={"status":"ok","liveFeed":False,"scheduleRecords":0,"liveVerified":0,"errors":[]}
    for version in ("1","2"):
        try:
            root=_get(f"https://feed.nascar.com/api/LiveFeed?v={version}",headers={"Referer":"https://www.nascar.com/","Origin":"https://www.nascar.com"})
            diagnostics["liveFeed"]=True
            rows=root if isinstance(root,list) else [root]
            for x in rows:
                if not isinstance(x,dict) or str(x.get("series_id") or x.get("seriesId"))!="3": continue
                rid=x.get("race_id") or x.get("raceId") or x.get("run_id"); nm=x.get("run_name") or x.get("event_name") or "NASCAR Craftsman Truck Series"; start=_iso(x.get("time_of_day_os") or x.get("start_time_utc") or x.get("start_time"))
                result.append({"league":"NASCAR Truck","title":nm,"start":start,"startUtc":start,"tag":"LIVE","status":"LIVE","state":"in","source":"nascar-livefeed-official","providerEventId":f"nascar:live:{rid}","liveEvidenceSource":"nascar-livefeed"}); diagnostics["liveVerified"]+=1
            if result: return result,diagnostics
            break
        except Exception as exc: diagnostics["errors"].append(f"livefeed:{type(exc).__name__}")
    diagnostics["status"]="blocked" if diagnostics["errors"] and not diagnostics["liveFeed"] else "no-live"
    return result,diagnostics


def main():
    if not FEED.exists(): raise SystemExit("official adapters: missing schedule_feed.json")
    payload=json.loads(FEED.read_text(encoding="utf-8")); events=[e for e in payload.get("events",[]) if isinstance(e,dict)]
    checked=str((payload.get("liveSweep") or {}).get("checkedAtUtc") or datetime.now(timezone.utc).isoformat().replace("+00:00","Z")); diagnostics={}; added=corroborated=0
    for name,fn in (("FIVB",_fivb),("NASCAR Truck",_nascar)):
        rows,diag=fn(); diagnostics[name]=diag
        for row in rows:
            ident=(_norm(row.get("league")),_norm(row.get("away")),_norm(row.get("home")))
            match=next((e for e in events if (_norm(e.get("league")),_norm(e.get("away")),_norm(e.get("home")))==ident),None)
            evidence={"providerEventId":row.get("providerEventId"),"provider":row.get("source"),"checkedAtUtc":checked}
            if match:
                match.update({"tag":"LIVE","status":"LIVE","state":"in","liveStateSource":"official-adapter","liveEvidence":evidence}); match.setdefault("liveEvidenceOfficial",[]).append(evidence); corroborated+=1
            else:
                row["liveEvidence"]=evidence; row["liveStateSource"]="official-adapter"; row["liveEvidenceOfficial"]=[evidence]; events.append(row); added+=1
    payload["events"]=events; payload["officialLiveAdapters"]={"checkedAtUtc":checked,"diagnostics":diagnostics,"liveAdded":added,"liveCorroborated":corroborated}; payload.setdefault("liveSweep",{})["officialAdapters"]=diagnostics
    FEED.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(payload["officialLiveAdapters"],indent=2))
if __name__=="__main__": main()
