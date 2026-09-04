#!/usr/bin/env python3
from sports_evidence import correlate

def test_agreement():
    e={'id':'1','title':'A @ B','league':'NFL','provider':'espn','status':'live','sourceUrl':'https://example.com/live'}
    r=correlate(e,[{'id':'1','title':'A @ B','league':'NFL','provider':'nfl-official','status':'live'}])
    assert r['verdict']=='LIVE' and r['confidence']>=0.8

def test_contradiction_is_visible():
    e={'id':'1','title':'A @ B','league':'NFL','provider':'espn','status':'live'}
    r=correlate(e,[{'id':'1','title':'A @ B','league':'NFL','provider':'nfl-official','status':'final'}])
    assert r['verdict']=='LIVE'
    assert any('contradiction' in x for x in r['reasons'])

def test_official_postponed_wins():
    e={'id':'1','title':'A @ B','league':'NFL','provider':'espn','status':'scheduled'}
    r=correlate(e,[{'id':'1','title':'A @ B','league':'NFL','provider':'nfl-official','status':'postponed'}])
    assert r['verdict']=='POSTPONED'

if __name__=='__main__':
    test_agreement(); test_contradiction_is_visible(); test_official_postponed_wins(); print('sports evidence tests: PASS')
