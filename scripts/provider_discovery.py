#!/usr/bin/env python3
"""Adaptive web discovery for missing sports schedules/sources.

Google is used as a discovery signal, never as the canonical schedule itself.
Candidates are probed, schema-checked and remembered before promotion.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = ROOT / "data" / "provider_knowledge.json"
USER_AGENT = "XSportsX-ProviderDiscovery/1.0 (+https://github.com/hurricanes92xx-hub/XSportsX-)"
MAX_BODY = 2_000_000

# Discovery is deliberately conservative. These are public/officially reachable
# web surfaces; it does not search for or recommend unauthorized stream sources.
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
BLOCKED_SCHEMES = {"file", "ftp", "javascript", "data"}


def _now():
    return datetime.now(timezone.utc)


def _load():
    try:
        value = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"schema": 1, "leagues": {}}
    except Exception:
        return {"schema": 1, "leagues": {}}


def _save(value):
    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = KNOWLEDGE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(KNOWLEDGE_FILE)


def _safe_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url)
        return p.scheme.lower() in {"http", "https"} and (p.hostname or "").lower() not in BLOCKED_HOSTS
    except Exception:
        return False


def _get(url: str, timeout: float = 6.0):
    if not _safe_url(url):
        return None, "unsafe-url", 0.0
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, text/calendar, text/html;q=0.9,*/*;q=0.5"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                return None, "response-too-large", time.monotonic() - started
            return body, str(response.headers.get("Content-Type", "")), time.monotonic() - started
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"[:220], time.monotonic() - started


def _google_cse(query: str):
    key, cx = os.getenv("GOOGLE_CSE_API_KEY"), os.getenv("GOOGLE_CSE_ID")
    if not key or not cx:
        return []
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode({"key": key, "cx": cx, "q": query, "num": 10, "safe": "active"})
    body, _, _ = _get(url, timeout=7)
    if not body:
        return []
    try:
        data = json.loads(body.decode("utf-8", "replace"))
        return [(x.get("link", ""), x.get("title", ""), x.get("snippet", "")) for x in data.get("items", []) if x.get("link")]
    except Exception:
        return []


def _google_news(query: str):
    # Google News RSS is a no-key Google discovery surface and is used when a
    # Programmable Search key is not configured.
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    body, _, _ = _get(url, timeout=7)
    if not body:
        return []
    try:
        root = ET.fromstring(body)
        out = []
        for item in root.findall(".//item")[:10]:
            link = (item.findtext("link") or "").strip()
            title = html.unescape((item.findtext("title") or "").strip())
            desc = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or "")).strip()
            if link:
                out.append((link, title, desc))
        return out
    except Exception:
        return []


def discovery_queries(league: str, event: dict | None = None):
    q = [f'"{league}" official schedule', f'"{league}" fixtures schedule 2026']
    if event:
        title = str(event.get("title") or "").strip()
        start = str(event.get("start") or event.get("startUtc") or "")[:10]
        if title:
            q.insert(0, f'"{title}" {start} official')
    return q


def _urls_from_html(text: str):
    urls = set()
    for match in re.findall(r'<(?:a|link)[^>]+href=["\']([^"\']+)', text, re.I):
        u = html.unescape(match)
        if u.startswith("/"):
            continue
        if _safe_url(u):
            urls.add(u)
    return list(urls)[:40]


def _event_from_obj(obj, league: str):
    if not isinstance(obj, dict):
        return None
    typ = obj.get("@type") or obj.get("type")
    if isinstance(typ, list):
        typ = " ".join(map(str, typ))
    typ = str(typ or "")
    if "sports" not in typ.lower() and not any(k in obj for k in ("startDate", "startUtc", "startTime", "dateStart")):
        return None
    start = obj.get("startDate") or obj.get("startUtc") or obj.get("startTime") or obj.get("dateStart")
    name = obj.get("name") or obj.get("title") or obj.get("eventName")
    if not start or not name:
        return None
    return {"sport": "", "league": league, "title": str(name)[:240], "startUtc": str(start), "start": str(start), "status": "scheduled", "state": "", "source": "discovery"}


def _extract_events(body: bytes, content_type: str, league: str):
    text = body.decode("utf-8", "replace")
    events = []
    ctype = content_type.lower()
    if "json" in ctype or text.lstrip().startswith(("{", "[")):
        try:
            data = json.loads(text)
            stack = data if isinstance(data, list) else [data]
            while stack:
                item = stack.pop()
                if isinstance(item, list): stack.extend(item)
                elif isinstance(item, dict):
                    event = _event_from_obj(item, league)
                    if event: events.append(event)
                    stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
        except Exception:
            pass
    elif "calendar" in ctype or "text/calendar" in ctype:
        current = {}
        for line in text.replace("\r", "").split("\n"):
            if line.startswith("BEGIN:VEVENT"): current = {}
            elif line.startswith("END:VEVENT"):
                if current.get("DTSTART") and current.get("SUMMARY"):
                    start = current["DTSTART"].replace("Z", "+00:00")
                    events.append({"sport": "", "league": league, "title": current["SUMMARY"], "startUtc": start, "start": start, "status": "scheduled", "state": "", "source": "discovery"})
                current = {}
            elif ":" in line:
                k, v = line.split(":", 1)
                current[k.split(";")[0]] = v.strip()
    else:
        for script in re.findall(r'<script[^>]*>(.*?)</script>', text, re.I | re.S):
            try:
                data = json.loads(html.unescape(script.strip()))
            except Exception:
                continue
            event = _event_from_obj(data, league)
            if event: events.append(event)
        for match in re.findall(r'\bhttps?://[^\s"\'<>]+', text):
            if any(x in match.lower() for x in (".json", ".xml", ".ics", "api")):
                pass
    return events[:200]


def _candidate_record(url, title, snippet, league):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return {"id": hashlib.sha256(url.encode()).hexdigest()[:16], "league": league, "endpoint": url, "host": host, "title": title[:200], "snippet": snippet[:400], "transport": "web", "responseSchema": "unknown", "lastSuccess": None, "lastFailure": None, "lastLatencyMs": None, "eventCount": 0, "coverageScore": 0.0, "reliabilityScore": 0.5, "confidence": 0.0, "observations": 0, "successes": 0, "failures": 0, "promoted": False, "expiresAt": (_now() + timedelta(days=7)).isoformat()}


def discover(league: str, event: dict | None = None, max_queries: int = 2):
    state = _load()
    bucket = state.setdefault("leagues", {}).setdefault(league, {"candidates": []})
    known = {x.get("endpoint") for x in bucket.get("candidates", [])}
    raw = []
    for query in discovery_queries(league, event)[:max_queries]:
        raw.extend(_google_cse(query) or _google_news(query))
    candidates = []
    for url, title, snippet in raw:
        if not _safe_url(url) or url in known:
            continue
        rec = _candidate_record(url, title, snippet, league)
        body, ctype, latency = _get(url)
        if body:
            found = _extract_events(body, ctype, league)
            rec["eventCount"] = len(found)
            rec["lastLatencyMs"] = round(latency * 1000, 1)
            rec["responseSchema"] = "json" if "json" in ctype.lower() else "ics" if "calendar" in ctype.lower() else "web"
            rec["successes"] = 1
            rec["observations"] = 1
            rec["coverageScore"] = min(1.0, len(found) / 10.0)
            rec["confidence"] = round(min(0.98, 0.35 + rec["coverageScore"] * 0.45 + (0.15 if "official" in title.lower() or ".gov" in rec["host"] else 0.0)), 3)
            rec["lastSuccess"] = _now().isoformat()
            rec["events"] = found
            if found:
                candidates.append(rec)
        else:
            rec["failures"] = 1
            rec["observations"] = 1
            rec["lastFailure"] = _now().isoformat()
    # Only successful candidates enter durable knowledge. This keeps random search
    # results from becoming provider dependencies.
    bucket["candidates"] = (bucket.get("candidates", []) + candidates)[-25:]
    state["schema"] = 1
    state["updatedAt"] = _now().isoformat()
    _save(state)
    return candidates


def promoted(league: str):
    state = _load()
    out = []
    for rec in state.get("leagues", {}).get(league, {}).get("candidates", []):
        if rec.get("promoted") and rec.get("confidence", 0) >= 0.65:
            out.append(rec)
    return sorted(out, key=lambda x: (float(x.get("confidence", 0)), float(x.get("coverageScore", 0))), reverse=True)


def promote_successful(league: str):
    state = _load()
    changed = False
    for rec in state.get("leagues", {}).get(league, {}).get("candidates", []):
        # Require repeated observations before promotion to prevent search poisoning.
        if rec.get("successes", 0) >= 2 and rec.get("confidence", 0) >= 0.65 and not rec.get("promoted"):
            rec["promoted"] = True
            changed = True
    if changed:
        state["updatedAt"] = _now().isoformat()
        _save(state)
    return promoted(league)


def discovery_events(league: str):
    events = []
    for rec in promoted(league):
        for event in rec.get("events", []) or []:
            item = dict(event)
            item["source"] = "discovery"
            item["discoveryEndpoint"] = rec.get("endpoint")
            events.append(item)
    return events
