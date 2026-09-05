#!/usr/bin/env python3
"""Patch the live sweep so late-night events are queried across UTC date boundaries."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
import re
import urllib.request
import live_sports_sweep as base

HEADERS = base.HEADERS

def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.read()

def _fetch_league(meta):
    name, sport, league, icon, _days = meta
    now = datetime.now(timezone.utc)
    dates = [(now + timedelta(days=offset)).strftime('%Y%m%d') for offset in (-1, 0, 1)]
    events = []
    last = None
    for day in dates:
        base_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={day}&limit=1000"
        root = None
        for url in (base_url.replace('https://site.api.espn.com', 'https://site.web.api.espn.com'), base_url):
            try:
                root = json.loads(_get(url))
                break
            except Exception as exc:
                last = str(exc)
        if root:
            raw = root.get('events')
            if isinstance(raw, list):
                events.extend(raw)
    seen = set()
    unique = []
    for event in events:
        key = str(event.get('id') or event.get('uid') or json.dumps(event, sort_keys=True))
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return name, unique, None if unique or not last else last

def _fetch_ncaa(meta):
    name, sport, division, icon = meta
    now = datetime.now(timezone.utc)
    days = [now.date() + timedelta(days=offset) for offset in (-1, 0, 1)]
    records = []
    errors = []
    for day in days:
        try:
            root = base._fetch_scoreboard_day(sport, division, day)
            if root:
                for game in __import__('providers.ncaa', fromlist=['_walk_games'])._walk_games(root):
                    event = base._normalize(game, name, icon)
                    if event:
                        records.append(event)
        except Exception as exc:
            errors.append(f'primary:{exc}')
        try:
            records.extend(base._fetch_espn_day(name, day))
        except Exception as exc:
            errors.append(f'espn:{exc}')
    seen = set()
    out = []
    for event in records:
        key = (str(event.get('away') or '').lower(), str(event.get('home') or '').lower(), str(event.get('start') or event.get('startUtc') or ''), str(event.get('providerEventId') or ''))
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    return name, out, None if out or not errors else '; '.join(errors)

base._fetch_league = _fetch_league
base._fetch_ncaa = _fetch_ncaa
base.main()
