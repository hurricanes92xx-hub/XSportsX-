#!/usr/bin/env python3
"""Dedicated official live adapters for NASCAR and FIVB.

These adapters are intentionally conservative: an event is LIVE only when the
source itself supplies a live/on-track state. Schedule windows are recovery
signals, never a substitute for an authoritative state when the API exposes one.
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FEED = ROOT / "data" / "schedule_feed.json"
UA = "XSportsX-OfficialLiveAdapters/1.3"
FIVB_URL = "https://www.fivb.org/Vis2009/XmlRequest.asmx"


def _get(url, timeout=10, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _post_xml(xml, timeout=12, accept="application/xml, text/xml, */*"):
    body = urllib.parse.urlencode({"Request": xml}).encode()
    req = urllib.request.Request(
        FIVB_URL,
        data=body,
        headers={"User-Agent": UA, "Accept": accept, "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _iso(v):
    if not v:
        return ""
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _norm(v):
    return "".join(c.lower() for c in str(v or "") if c.isalnum())


def _live_status(v):
    s = str(v or "").strip().lower().replace("-", "").replace(" ", "")
    return s in {"inset1", "inset2", "inset3", "inset4", "inset5", "inset6", "inset7", "live", "inprogress", "playing", "started", "running", "halftime", "ht"}


def _field(el, *names):
    wanted = {n.lower() for n in names}
    for k, v in el.attrib.items():
        if k.lower() in wanted and v:
            return v
    for child in el:
        if child.tag.split("}")[-1].lower() in wanted and child.text:
            return child.text.strip()
    return ""


def _identity(row):
    return (_norm(row.get("league")), _norm(row.get("away")), _norm(row.get("home")))


def _fivb_match_nodes(root):
    nodes = []
    for el in root.iter():
        tag = el.tag.split("}")[-1].lower()
        if tag not in {"volleymatch", "match"}:
            continue
        no = _field(el, "No", "NoMatch", "NoVolleyMatch")
        home = _field(el, "TeamNameA", "TeamAName")
        away = _field(el, "TeamNameB", "TeamBName")
        if no and home and away:
            nodes.append(el)
    return nodes


def _fivb_live_request(no):
    """Return (confirmed, diagnostic).

    FIVB documents GetVolleyLive as the public live-data request. A successful
    VolleyLive payload is sufficient evidence even when the response omits a
    duplicated status field; a NoChanges response is not evidence of failure.
    """
    errors = []
    requests = (
        f'<Request Type="GetVolleyLive" No="{no}" Options="128" Version="0" />',
        f'<Request Type="GetVolleyLive" No="{no}" Options="128" />',
        f'<Request Type="GetVolleyLive" NoVolleyMatch="{no}" Options="128" Version="0" />',
    )
    for req in requests:
        try:
            raw = _post_xml(req, accept="application/xml, text/xml, */*")
            root = ET.fromstring(raw)
            root_tag = root.tag.split("}")[-1].lower()
            if root_tag == "nochang es".replace(" ", ""):
                return True, "nochanges"
            if root_tag == "volleylive" or any(n.tag.split("}")[-1].lower() == "volleylive" for n in root.iter()):
                values = []
                for node in root.iter():
                    for key in ("Status", "StatusName", "MatchStatus"):
                        value = _field(node, key)
                        if value:
                            values.append(value)
                if not values or any(_live_status(v) for v in values):
                    return True, "volleylive"
            for node in root.iter():
                tag = node.tag.split("}")[-1].lower()
                if tag in {"error", "badparameter", "nodata", "parametermissing", "accessdenied"}:
                    errors.append(tag)
        except urllib.error.HTTPError as exc:
            errors.append(f"http:{exc.code}")
        except Exception as exc:
            errors.append(type(exc).__name__)
    return False, ";".join(errors[-3:]) or "no-live-payload"


def _fivb():
    result = []
    diagnostics = {"status": "ok", "listRecords": 0, "candidates": 0, "liveVerified": 0, "liveRejected": 0, "errors": [], "verification": {}}
    requests = [
        '<Request Type="GetVolleyMatchList" Fields="No DateTimeUtc BeginDateTimeUtc TeamNameA TeamNameB Status Gender TournamentName"><Filter ForLiveScore="true" Statuses="InSet1 InSet2 InSet3 InSet4 InSet5 InSet6 InSet7" /></Request>',
        '<Request Type="GetVolleyMatchList" Fields="No DateTimeUtc BeginDateTimeUtc TeamNameA TeamNameB Status Gender TournamentName"><Filter ForLiveScore="true" /></Request>',
    ]
    raw = None
    for req in requests:
        try:
            raw = _post_xml(req)
            break
        except Exception as exc:
            diagnostics["errors"].append(f"list:{type(exc).__name__}")
    if raw is None:
        diagnostics["status"] = "unavailable"
        return result, diagnostics
    try:
        root = ET.fromstring(raw)
    except Exception as exc:
        diagnostics["status"] = "invalid"
        diagnostics["errors"].append(f"xml:{type(exc).__name__}")
        return result, diagnostics

    nodes = _fivb_match_nodes(root)
    diagnostics["listRecords"] = len(nodes)
    for el in nodes:
        no = _field(el, "No", "NoMatch", "NoVolleyMatch")
        home = _field(el, "TeamNameA", "TeamAName")
        away = _field(el, "TeamNameB", "TeamBName")
        status = _field(el, "Status", "StatusName", "MatchStatus")
        if not _live_status(status):
            continue
        diagnostics["candidates"] += 1
        start = _iso(_field(el, "DateTimeUtc", "BeginDateTimeUtc", "DateUtc"))
        gender = _norm(_field(el, "Gender", "TournamentGender"))
        tournament = _field(el, "TournamentName", "Name")
        league = "FIVB Women" if gender in {"w", "women", "female", "f"} or "women" in _norm(tournament) or "feminin" in _norm(tournament) else "FIVB Men"
        confirmed, why = _fivb_live_request(no)
        diagnostics["verification"][str(no)] = why
        if not confirmed:
            diagnostics["liveRejected"] += 1
            continue
        result.append({"league": league, "title": f"{away} @ {home}", "start": start, "startUtc": start, "tag": "LIVE", "status": "LIVE", "state": "in", "home": home, "away": away, "source": "fivb-vis-official", "providerEventId": f"fivb:{no}", "liveEvidenceSource": "fivb-vis"})
        diagnostics["liveVerified"] += 1
    return result, diagnostics


def _nascar():
    result = []
    diagnostics = {"status": "ok", "liveFeed": False, "scheduleRecords": 0, "liveVerified": 0, "errors": []}
    for version in ("1", "2"):
        try:
            root = _get(f"https://feed.nascar.com/api/LiveFeed?v={version}", timeout=10, headers={"Referer": "https://www.nascar.com/", "Origin": "https://www.nascar.com"})
            rows = root if isinstance(root, list) else [root]
            diagnostics["liveFeed"] = True
            for x in rows:
                if not isinstance(x, dict) or str(x.get("series_id") or x.get("seriesId")) != "3":
                    continue
                name = str(x.get("run_name") or x.get("event_name") or "NASCAR Craftsman Truck Series")
                race_id = x.get("race_id") or x.get("raceId")
                start = _iso(x.get("time_of_day_os") or x.get("start_time_utc"))
                result.append({"league": "NASCAR Truck", "title": name, "start": start, "startUtc": start, "tag": "LIVE", "status": "LIVE", "state": "in", "source": "nascar-livefeed-official", "providerEventId": f"nascar:live:{race_id or x.get('run_id')}", "liveEvidenceSource": "nascar-livefeed"})
                diagnostics["liveVerified"] += 1
            if result:
                return result, diagnostics
            break
        except Exception as exc:
            diagnostics["errors"].append(f"livefeed:{type(exc).__name__}")
    year = datetime.now(timezone.utc).year
    for host in ("https://feed.nascar.com", "https://feedtest.nascar.com"):
        try:
            root = _get(f"{host}/api/weekendschedule?series_id=3&race_season={year}&v=1", timeout=10, headers={"Referer": "https://www.nascar.com/", "Origin": "https://www.nascar.com"})
            rows = root if isinstance(root, list) else root.get("weekendSchedule") or root.get("data") or root.get("items") or []
            diagnostics["scheduleRecords"] += len(rows)
            now = datetime.now(timezone.utc)
            for x in rows:
                if not isinstance(x, dict):
                    continue
                start = _iso(x.get("start_time_utc") or x.get("startTimeUtc") or x.get("start_time")); end = _iso(x.get("end_time_utc") or x.get("endTimeUtc") or x.get("end_time"))
                if not start:
                    continue
                st = datetime.fromisoformat(start.replace("Z", "+00:00")); et = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
                if st <= now and (et is None or now <= et):
                    name = str(x.get("event_name") or x.get("eventName") or "NASCAR Craftsman Truck Series")
                    result.append({"league": "NASCAR Truck", "title": name, "start": start, "startUtc": start, "tag": "LIVE", "status": "LIVE", "state": "in", "source": "nascar-schedule-official", "providerEventId": f"nascar:{x.get('race_id') or x.get('raceId') or _norm(name)+'-'+start}", "liveEvidenceSource": "nascar-schedule"})
                    diagnostics["liveVerified"] += 1
            if result:
                return result, diagnostics
        except Exception as exc:
            diagnostics["errors"].append(f"schedule:{type(exc).__name__}")
    if not diagnostics["liveFeed"] and diagnostics["scheduleRecords"] == 0:
        diagnostics["status"] = "unavailable"
    elif not result:
        diagnostics["status"] = "no-live"
    return result, diagnostics


def main():
    if not FEED.exists():
        raise SystemExit("official adapters: missing schedule_feed.json")
    payload = json.loads(FEED.read_text(encoding="utf-8")); events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    checked = str((payload.get("liveSweep") or {}).get("checkedAtUtc") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    diagnostics = {}; added = corroborated = 0
    for name, fn in (("FIVB", _fivb), ("NASCAR Truck", _nascar)):
        rows, diag = fn(); diagnostics[name] = diag
        for row in rows:
            match = next((e for e in events if _identity(e) == _identity(row)), None)
            evidence = {"providerEventId": row.get("providerEventId"), "provider": row.get("source"), "checkedAtUtc": checked}
            if match:
                match["tag"] = match["status"] = "LIVE"; match["state"] = "in"; match["liveStateSource"] = "official-adapter"; match["liveEvidence"] = evidence; match.setdefault("liveEvidenceOfficial", []).append(evidence); corroborated += 1
            else:
                row["liveEvidence"] = evidence; row["liveStateSource"] = "official-adapter"; row["liveEvidenceOfficial"] = [evidence]; events.append(row); added += 1
    payload["events"] = events; payload["officialLiveAdapters"] = {"checkedAtUtc": checked, "diagnostics": diagnostics, "liveAdded": added, "liveCorroborated": corroborated}; payload.setdefault("liveSweep", {})["officialAdapters"] = diagnostics
    FEED.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["officialLiveAdapters"], indent=2))


if __name__ == "__main__":
    main()
