#!/usr/bin/env python3
"""Phase 2 schedule repairs with Phase 1-style source and date safeguards.

Phase 2 starts with NBA and NLL. A source is not considered repaired merely because
it returned HTTP 200 or parsed rows: at least one current/future in-season event must
survive dedupe before an official/provider failure is cleared.
"""
from __future__ import annotations
import json, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'data' / 'schedule_feed.json'
POLICY = ROOT / 'data' / 'schedule_season_policy.json'
HEADERS = {
    'User-Agent': 'XSportsX-Schedule/5.6',
    'Accept': 'application/json,text/html,*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.nba.com',
    'Referer': 'https://www.nba.com/',
}
LOOKAHEAD_DAYS = 370


def fetch(url, accept=None):
    h = dict(HEADERS)
    if accept:
        h['Accept'] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read()


def get_json(url):
    return json.loads(fetch(url, 'application/json,text/plain,*/*').decode('utf-8', 'ignore'))


def iso(v):
    if v is None:
        return None
    s = str(v).strip()
    for candidate in (s, s.replace('Z', '+00:00'), s.replace('z', '+00:00')):
        try:
            return datetime.fromisoformat(candidate).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        except ValueError:
            pass
    return None


def add(events, league, title, start, source, icon):
    start = iso(start)
    if not start or not title:
        return False
    key = (league, title, start)
    if key in {(e.get('league'), e.get('title'), e.get('start')) for e in events}:
        return False
    events.append({'league': league, 'title': title, 'start': start, 'tag': 'UPCOMING', 'icon': icon, 'source': source})
    return True


def window_ok(dt, league, policy, reference):
    horizon = reference + timedelta(days=LOOKAHEAD_DAYS)
    season = (policy.get('leagueWindows') or {}).get(league)
    if not (reference <= dt <= horizon):
        return False
    if not season:
        return True
    month_day = (dt.month, dt.day)
    start = tuple(map(int, season[0]))
    end = tuple(map(int, season[1]))
    return start <= month_day <= end if start <= end else (month_day >= start or month_day <= end)


def validate_added(events, league, before_keys, policy, reference):
    after = []
    for e in events:
        if e.get('league') != league:
            continue
        key = (e.get('league'), e.get('title'), e.get('start'))
        if key in before_keys:
            continue
        try:
            dt = datetime.fromisoformat(str(e.get('start')).replace('Z', '+00:00')).astimezone(timezone.utc)
        except Exception:
            continue
        if window_ok(dt, league, policy, reference):
            after.append(dt)
    return after


def repair_nba(events, report, failures, policy, reference):
    # NBA's public CDN schedule is the same source used by nba.com. The alternate
    # _1 endpoint has historically drifted, so try the current endpoint first and
    # only fall back to _1 if the current payload is unavailable.
    urls = [
        'https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json',
        'https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json',
    ]
    before = {(e.get('league'), e.get('title'), e.get('start')) for e in events}
    parsed = 0
    added = 0
    source_used = None
    errors = []
    for url in urls:
        try:
            root = get_json(url)
            dates = ((root.get('leagueSchedule') or {}).get('gameDates') or []) if isinstance(root, dict) else []
            rows = []
            for day in dates:
                rows.extend(day.get('games') or [])
            if not rows:
                raise RuntimeError('schedule payload contained zero games')
            source_used = url
            parsed = len(rows)
            for game in rows:
                start = game.get('gameDateTimeUTC') or game.get('gameDateTimeEst') or game.get('gameDate')
                away = game.get('awayTeam') or {}
                home = game.get('homeTeam') or {}
                away_name = away.get('teamName') or away.get('teamCity') or away.get('teamTricode')
                home_name = home.get('teamName') or home.get('teamCity') or home.get('teamTricode')
                title = f'{away_name} @ {home_name}' if away_name and home_name else game.get('gameLabel') or 'NBA'
                if add(events, 'NBA', title, start, 'cdn.nba.com scheduleLeagueV2', '🏀'):
                    added += 1
            break
        except Exception as exc:
            errors.append(f'{url}: {exc}')

    valid_new = validate_added(events, 'NBA', before, policy, reference)
    report['NBA'] = {
        'source': 'NBA official CDN scheduleLeagueV2',
        'source_url': source_used,
        'parsed': parsed,
        'added': added,
        'current_future_added': len(valid_new),
        'reference': reference.isoformat().replace('+00:00', 'Z'),
        'errors': errors,
    }
    if valid_new:
        failures[:] = [x for x in failures if x != 'NBA']
        print(f'PHASE2 NBA: source healthy, parsed={parsed}, added={added}, current_future_added={len(valid_new)}')
    else:
        print(f'NO REPAIR NBA: parsed={parsed}, added={added}, current_future_added=0')


def probe_nll(events, report, failures, policy, reference):
    # NLL's official schedule page currently exposes 2025-26. The league has
    # announced that the new YinzCam-powered platform launches for the November
    # 2026 season, but the 2026-27 fixture list is not yet published on the official
    # schedule page. Treat that as legitimate offseason/awaiting-publication rather
    # than inventing dates or clearing a source failure on an empty response.
    url = 'https://www.nll.com/schedule/full-schedule/'
    try:
        text = fetch(url, 'text/html,*/*').decode('utf-8', 'ignore')
        seasons = sorted(set(re.findall(r'20\d\d-\d\d', text)))
        has_2026_27 = '2026-27' in seasons
        current_future = []
        for e in events:
            if e.get('league') != 'NLL':
                continue
            try:
                dt = datetime.fromisoformat(str(e.get('start')).replace('Z', '+00:00')).astimezone(timezone.utc)
            except Exception:
                continue
            if window_ok(dt, 'NLL', policy, reference):
                current_future.append(dt)
        report['NLL'] = {
            'source': 'NLL official full schedule page',
            'published_seasons': seasons,
            '2026_27_published': has_2026_27,
            'current_future_existing': len(current_future),
            'status': 'awaiting_2026_27_publication' if not has_2026_27 else 'published',
        }
        if has_2026_27 and current_future:
            failures[:] = [x for x in failures if x != 'NLL']
        print(f'PHASE2 NLL: published_2026_27={has_2026_27}, current_future_existing={len(current_future)}')
    except Exception as exc:
        report['NLL'] = {'source': 'NLL official full schedule page', 'status': 'probe_failed', 'error': str(exc)}
        print(f'NO REPAIR NLL: {exc}')


def main():
    p = json.loads(FEED.read_text(encoding='utf-8'))
    events = p.get('events') or []
    failures = list(p.get('officialSourceFailures') or [])
    policy = json.loads(POLICY.read_text(encoding='utf-8')) if POLICY.exists() else {}
    try:
        reference = datetime.fromisoformat(str(p.get('generatedAt')).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        reference = datetime.now(timezone.utc)
    report = p.setdefault('phase2RepairReport', {})
    repair_nba(events, report, failures, policy, reference)
    probe_nll(events, report, failures, policy, reference)
    p['events'] = events
    p['officialSourceFailures'] = failures
    p['eventCounts'] = {k: sum(1 for e in events if e.get('league') == k) for k in sorted({e.get('league') for e in events if e.get('league')})}
    p['generatedAt'] = datetime.now(timezone.utc).isoformat()
    FEED.write_text(json.dumps(p, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('PHASE2 failures remaining:', failures)
    print(f'PHASE2 complete: {len(events)} events across {len(p["eventCounts"])} leagues')


if __name__ == '__main__':
    main()
