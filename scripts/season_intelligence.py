#!/usr/bin/env python3
"""Deterministic season/activity intelligence for the XSportsX scheduler."""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; POLICY_PATH=ROOT/'data'/'schedule_season_policy.json'
def _load_policy():
    try:return json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    except Exception:return {'default':{'unknownLeagueMode':'active','inactiveProbeHours':24,'recentActivityDays':45},'leagueWindows':{}}
def _month_day(v):
    """Accept [month,day] and legacy scalar month safely."""
    if isinstance(v,(list,tuple)) and len(v)>=2:return int(v[0]),int(v[1])
    if isinstance(v,int):return int(v),1
    if isinstance(v,str):
        parts=v.replace('/','-').split('-')
        if len(parts)>=2:return int(parts[0]),int(parts[1])
    raise ValueError(f'invalid season date: {v!r}')
def _window_active(today:date,windows):
    if not windows:return True
    md=today.month*100+today.day
    for window in windows:
        if not isinstance(window,(list,tuple)) or len(window)!=2:continue
        start,end=window
        sm,sd=_month_day(start); em,ed=_month_day(end)
        start_md,end_md=sm*100+sd,em*100+ed
        if start_md<=end_md:
            if start_md<=md<=end_md:return True
        elif md>=start_md or md<=end_md:return True
    return False
def _parse_event_time(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None
def analyze(league,previous_events=None,now=None):
    policy=_load_policy(); default=policy.get('default',{}); windows=policy.get('leagueWindows',{}).get(league); now=now or datetime.now(timezone.utc); today=now.date(); observed=[]
    for event in previous_events or []:
        if event.get('league')!=league:continue
        dt=_parse_event_time(event.get('start') or event.get('startUtc'))
        if dt:observed.append(dt)
    lookahead=now+timedelta(days=370); recent_cutoff=now-timedelta(days=int(default.get('recentActivityDays',45))); upcoming=[dt for dt in observed if now-timedelta(hours=12)<=dt<=lookahead]; recent=[dt for dt in observed if recent_cutoff<=dt<=now+timedelta(days=1)]; configured_active=_window_active(today,windows) if windows else None; observed_active=bool(upcoming or recent); active=observed_active or configured_active is True or (configured_active is None and default.get('unknownLeagueMode')=='active'); refresh_class='active' if active else 'inactive'; probe_hours=int(default.get('activeProbeHours',1) if active else default.get('inactiveProbeHours',24)); reason='observed_activity' if observed_active else ('season_window' if active else 'outside_season_window')
    return {'league':league,'active':active,'class':refresh_class,'probeHours':probe_hours,'reason':reason,'configuredSeason':windows or [],'observedUpcoming':len(upcoming),'observedRecent':len(recent)}
def should_refresh_provider(league,previous_events=None,now=None):return bool(analyze(league,previous_events,now)['active'])
def report(leagues,previous_events=None):return [analyze(league,previous_events) for league in leagues]
