#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from sports_agent import Evidence, ToolRegistry, deterministic_plan, run
from sports_knowledge_graph import load, observe_feed


def test_allowlist() -> None:
    evidence = Evidence("e1", "Test", "LIVE", 0.9, "refresh_live_evidence", ["live"], "espn", False)
    registry = ToolRegistry()
    result = registry.execute("refresh_live_evidence", evidence)
    assert result["status"] == "completed"
    assert registry.execute("rm -rf /", evidence)["status"] == "rejected"


def test_source_gap_is_escalated() -> None:
    evidence = Evidence("e1", "Test", "LIVE", 0.9, "refresh_live_evidence", ["live"], "espn", False)
    assert deterministic_plan(evidence)["action"] == "discover_event_source_metadata"


def test_real_discovery_tool_is_bounded() -> None:
    evidence = Evidence("e1", "Test", "UPCOMING", 0.5, "discover_schedule_provider", ["missing source"], "espn", False, league="")
    result = ToolRegistry().execute("discover_schedule_provider", evidence)
    assert result["status"] == "skipped"
    assert result["reason"] == "missing-league"


def test_graph_and_agent_contract() -> None:
    feed = {"events": [{"id": "e1", "sport": "football", "league": "NFL", "title": "A @ B", "startUtc": "2099-01-01T20:00:00Z", "status": "scheduled", "home": "B", "away": "A", "provider": "test", "broadcast": "Test Network"}]}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        feed_path = root / "feed.json"
        memory = root / "memory.json"
        graph = root / "graph.json"
        feed_path.write_text(json.dumps(feed), encoding="utf-8")
        stats = observe_feed(feed, graph)
        assert stats["nodes"] >= 6
        result = run(feed_path, memory, graph)
        assert result["schema"] == 2
        written = json.loads(feed_path.read_text(encoding="utf-8"))
        assert written["sportsAgent"]["schema"] == 2
        assert load(graph)["stats"]["edges"] >= 3


if __name__ == "__main__":
    test_allowlist()
    test_source_gap_is_escalated()
    test_real_discovery_tool_is_bounded()
    test_graph_and_agent_contract()
    print("sports agent tests: PASS")
