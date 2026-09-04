#!/usr/bin/env python3
import tempfile, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sports_prediction import predict_event, run

NOW=datetime(2026,9,4,12,0,tzinfo=timezone.utc)

def test_missing_source_becomes_urgent():
    event={"id":"e1","league":"NFL","title":"A @ B","startUtc":(NOW+timedelta(minutes=10)).isoformat(),"intelligencePhase":"UPCOMING","intelligenceConfidence":.9}
    p=predict_event(event,{"nodes":{},"edges":[]},NOW)
    assert p["recommendedAction"]=="discover_event_source_metadata" and p["risk"]>=.55

def test_existing_source_prewarms():
    event={"id":"e2","league":"NFL","title":"A @ B","startUtc":(NOW+timedelta(minutes=10)).isoformat(),"sourceUrl":"https://example.com/live","intelligencePhase":"UPCOMING","intelligenceConfidence":.9}
    p=predict_event(event,{"nodes":{},"edges":[]},NOW)
    assert p["recommendedAction"]=="warm_source"

def test_provider_history_selects_best_candidate():
    event={"id":"e3","league":"NFL","title":"A @ B","startUtc":(NOW+timedelta(hours=3)).isoformat(),"intelligencePhase":"UPCOMING","intelligenceConfidence":.9}
    knowledge={"leagues":{"NFL":{"candidates":[{"provider":"slow","successes":2,"failures":3,"confidence":.5,"latencyMs":4000},{"provider":"good","successes":9,"failures":1,"confidence":.9,"latencyMs":300}]}}}
    p=predict_event(event,{"nodes":{},"edges":[]},NOW,knowledge)
    assert p["recommendedProvider"]=="good"

def test_contract():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); feed=root/'feed.json'; graph=root/'graph.json'; knowledge=root/'knowledge.json'
        feed.write_text(json.dumps({"events":[]}),encoding='utf-8'); graph.write_text(json.dumps({"nodes":{},"edges":[]}),encoding='utf-8'); knowledge.write_text(json.dumps({"leagues":{}}),encoding='utf-8')
        result=run(feed,graph,knowledge_path=knowledge)
        assert result["schema"]==2
        assert "sportsPredictions" in json.loads(feed.read_text())

if __name__=='__main__':
    test_missing_source_becomes_urgent(); test_existing_source_prewarms(); test_provider_history_selects_best_candidate(); test_contract(); print('sports prediction tests: PASS')
