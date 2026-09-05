#!/usr/bin/env python3
"""Deterministic regression tests for the autonomous coverage investigator."""
from __future__ import annotations
from datetime import datetime,timezone
import sports_intelligence_loop as intel


def ev(title='Test FC vs Test United', league='EPL', start='2026-09-04T19:00:00Z', state='pre'):
    return {'id':f'{league}-{title}','sport':'Soccer','league':league,'title':title,'startUtc':start,'start':start,'state':state,'status':'scheduled'}


def test_live_detection():
    assert intel.is_live(ev(state='in'))
    assert intel.is_live(ev(state='halftime'))
    assert not intel.is_live(ev(state='post'))


def test_provider_gap_requires_identity_match():
    canonical=[ev('Alpha FC vs Beta FC')]
    provider=ev('Gamma FC vs Delta FC')
    assert not any(intel.identity_match(c,provider) for c in canonical)


def test_promotion_requires_evidence():
    canonical=[]; candidate=ev()
    assert intel.promote(canonical,candidate,['provider:EPL']) is True
    assert canonical[0]['aiRecovered'] is True
    assert canonical[0]['intelligenceSource']=='autonomous-coverage-audit'


def test_sport_context_is_available():
    ctx=intel.sport_awareness.ai_context(ev())
    assert ctx['sportKey']
    assert ctx['sportProfile']


if __name__=='__main__':
    test_live_detection();test_provider_gap_requires_identity_match();test_promotion_requires_evidence();test_sport_context_is_available();print('sports intelligence loop tests passed')
