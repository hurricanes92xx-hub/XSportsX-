#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone, timedelta
from live_sports_sweep import _espn_event, _parse_dt, _state, _within_window
from normalize_schedule_feed import normalize_ufc_event

class LiveSweepTests(unittest.TestCase):
    def test_provider_states(self):
        self.assertEqual(_state({'type': {'state': 'in', 'detail': '2nd Quarter'}}), 'LIVE')
        self.assertEqual(_state({'type': {'state': 'pre', 'detail': 'Scheduled'}}), 'UPCOMING')
        self.assertEqual(_state({'type': {'state': 'post', 'detail': 'Final'}}), 'FINAL')
        self.assertEqual(_state({'type': {'state': 'in', 'detail': 'Halftime'}}), 'LIVE')
        self.assertEqual(_state({'type': {'state': 'pre', 'detail': 'Set 2'}}), 'LIVE')

    def test_espn_event_bridges_state_into_android_contract(self):
        event = _espn_event('NCAA Football', '🏈', {
            'id': '123',
            'date': '2026-09-05T01:00:00Z',
            'name': 'Miami Hurricanes at Stanford Cardinal',
            'competitions': [{
                'competitors': [
                    {'homeAway': 'home', 'team': {'id': '1', 'shortDisplayName': 'Stanford'}},
                    {'homeAway': 'away', 'team': {'id': '2', 'shortDisplayName': 'Miami'}},
                ],
                'status': {'type': {'state': 'in', 'detail': '2nd Quarter'}, 'displayClock': '08:21'},
            }],
        })
        self.assertEqual(event['tag'], 'LIVE')
        self.assertEqual(event['status'], 'LIVE')
        self.assertEqual(event['state'], 'in')
        self.assertEqual(event['providerEventId'], 'espn:123')
        self.assertEqual(event['home'], 'Stanford')
        self.assertEqual(event['away'], 'Miami')

    def test_timing_inference_is_bounded(self):
        now = datetime.now(timezone.utc)
        fresh = {'sport': 'soccer', 'startUtc': (now - timedelta(minutes=80)).isoformat().replace('+00:00', 'Z')}
        stale = {'sport': 'soccer', 'startUtc': (now - timedelta(hours=4)).isoformat().replace('+00:00', 'Z')}
        self.assertTrue(_within_window(fresh, now))
        self.assertFalse(_within_window(stale, now))
        self.assertIsNotNone(_parse_dt(fresh['startUtc']))

    def test_ufc_paris_has_only_official_two_sessions(self):
        early = normalize_ufc_event({
            'league': 'UFC', 'title': 'UFC Fight Night: Hooker vs Parnasse — Early Prelims',
            'startUtc': '2026-09-05T21:00:00Z', 'start': '2026-09-05T21:00:00Z'
        })
        duplicate = normalize_ufc_event({
            'league': 'UFC', 'title': 'Hooker @ Parnasse',
            'startUtc': '2026-09-05T19:00:00Z', 'start': '2026-09-05T19:00:00Z'
        })
        prelim = normalize_ufc_event({
            'league': 'UFC', 'title': 'UFC Fight Night: Hooker vs Parnasse — Prelims',
            'startUtc': '2026-09-05T17:00:00Z', 'start': '2026-09-05T17:00:00Z'
        })
        main = normalize_ufc_event({
            'league': 'UFC', 'title': 'UFC Fight Night: Hooker vs Parnasse — Main Card',
            'startUtc': '2026-09-05T21:00:00Z', 'start': '2026-09-05T21:00:00Z'
        })
        self.assertIsNone(early)
        self.assertIsNone(duplicate)
        self.assertEqual(prelim['startUtc'], '2026-09-05T16:00:00Z')
        self.assertEqual(main['startUtc'], '2026-09-05T19:00:00Z')

if __name__ == '__main__':
    unittest.main()
