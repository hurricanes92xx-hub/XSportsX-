#!/usr/bin/env python3
"""FIVB VIS public volleyball schedule provider.

VIS exposes public volleyball match data through the documented single-request
GET form.  Important: current FIVB continental championships are organized by
AVC/CEV/NORCECA/CAVB/CSV, so filtering TournamentOrganizerType=Fivb drops the
very competitions we need.  We therefore filter by gender/date only.
"""
from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

BASE_URL = "https://www.fivb.org/Vis2009/XmlRequest.asmx?Request="
HEADERS = {
    "User-Agent": "XSportsX-Schedule/1.0",
    "Accept": "application/xml",
}


def _iso(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return str(value)


def _status(value: str | None) -> str:
    s = str(value or "").strip().lower().replace(" ", "")
    if s in {"inset1", "inset2", "inset3", "inset4", "inset5", "inset6", "inset7", "5", "7", "9", "11", "13", "15", "17", "19", "21", "23"}:
        return "LIVE"
    if s in {"finished", "officialresult", "corrected", "closed", "24", "25", "26"}:
        return "FINAL"
    return "UPCOMING"


def _child_attr(item: ET.Element, child_name: str, attr: str) -> str:
    for child in item:
        if child.tag.split("}")[-1] == child_name:
            return str(child.attrib.get(attr) or "").strip()
    return ""


def fetch(league: str, icon: str):
    gender = {"FIVB Men": "M", "FIVB Women": "W"}.get(league)
    if not gender:
        return True, [], "unsupported league"

    now = datetime.now(timezone.utc)
    first = (now - timedelta(hours=12)).date().isoformat()
    last = (now + timedelta(days=30)).date().isoformat()

    # TournamentGenders is the documented VolleyMatchFilter property.
    # Do NOT add TournamentOrganizerType=Fivb: the 2026 continental
    # championships are run by the confederations, not the FIVB organizer.
    fields = (
        "No DateTimeUtc BeginDateTimeUtc EndDateTimeUtc "
        "TeamAName TeamBName TeamNameA TeamNameB Status "
        "TournamentName TournamentTitle TournamentCode"
    )
    request_xml = (
        f'<Request Type="GetVolleyMatchList" Fields="{fields}">'
        f'<Filter FirstDate="{first}" LastDate="{last}" '
        f'TournamentGenders="{gender}"/>'
        f'<Relation Name="TeamA" Fields="Code Name" />'
        f'<Relation Name="TeamB" Fields="Code Name" />'
        f'<Relation Name="Tournament" Fields="Code Name" />'
        f'</Request>'
    )
    url = BASE_URL + urllib.parse.quote(request_xml, safe="")
    request = urllib.request.Request(url, headers=HEADERS, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            root = ET.fromstring(response.read())
    except Exception as exc:
        return False, [], f"{type(exc).__name__}: {exc}"

    out = []
    for item in root.iter():
        if item.tag.split("}")[-1] != "VolleyballMatch":
            continue
        a = item.attrib
        start = _iso(a.get("DateTimeUtc") or a.get("BeginDateTimeUtc"))
        home = str(a.get("TeamAName") or a.get("TeamNameA") or "").strip()
        away = str(a.get("TeamBName") or a.get("TeamNameB") or "").strip()
        home = home or _child_attr(item, "TeamA", "Name")
        away = away or _child_attr(item, "TeamB", "Name")
        if not start or not (home and away):
            continue

        tournament = str(
            a.get("TournamentTitle")
            or a.get("TournamentName")
            or _child_attr(item, "Tournament", "Name")
            or "FIVB"
        ).strip()
        tournament_code = str(a.get("TournamentCode") or _child_attr(item, "Tournament", "Code") or "").strip()
        title = f"{away} @ {home}"
        match_no = a.get("No") or a.get("NoInTournament") or start
        out.append({
            "league": league,
            "title": title,
            "start": start,
            "tag": _status(a.get("Status")),
            "icon": icon,
            "source": "fivb-vis",
            "home": home,
            "away": away,
            "providerEventId": f"fivb:{match_no}",
            "tournament": tournament,
            "tournamentCode": tournament_code,
        })
    return True, out, ""
