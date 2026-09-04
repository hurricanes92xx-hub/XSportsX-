#!/usr/bin/env python3
"""FIVB VIS public volleyball schedule provider.

VIS documents the single-request GET form as:
  XmlRequest.asmx?Request=<Request ...>
The endpoint is public and supports XML responses.
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


def fetch(league: str, icon: str):
    gender = {"FIVB Men": "M", "FIVB Women": "W"}.get(league)
    if not gender:
        return True, [], "unsupported league"

    # Keep a small overlap before now so an in-progress match is not missed,
    # while looking 30 days forward for the command center schedule.
    now = datetime.now(timezone.utc)
    first = (now - timedelta(hours=12)).date().isoformat()
    last = (now + timedelta(days=30)).date().isoformat()

    fields = "No DateTimeUtc BeginDateTimeUtc EndDateTimeUtc TeamNameA TeamNameB Status TournamentName TournamentTitle TournamentCode"
    request_xml = (
        f'<Request Type="GetVolleyMatchList" Fields="{fields}">'
        f'<Filter FirstDate="{first}" LastDate="{last}" '
        f'TournamentGenders="{gender}" TournamentOrganizerType="Fivb"/>'
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
        home = str(a.get("TeamNameA") or "").strip()
        away = str(a.get("TeamNameB") or "").strip()
        if not start or not (home and away):
            continue
        tournament = str(a.get("TournamentTitle") or a.get("TournamentName") or "FIVB").strip()
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
        })
    return True, out, ""
