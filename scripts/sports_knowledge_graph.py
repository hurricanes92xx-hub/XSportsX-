#!/usr/bin/env python3
"""Compact persistent knowledge graph for the XSportsX agent.

The graph stores only derived sports relationships and operational evidence.
Secrets and playback credentials are deliberately excluded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1
MAX_NODES = 20000
MAX_EDGES = 50000


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty() -> dict[str, Any]:
    return {"schema": SCHEMA, "updatedAt": None, "nodes": {}, "edges": [], "stats": {}}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty()
        data.setdefault("schema", SCHEMA)
        data.setdefault("nodes", {})
        data.setdefault("edges", [])
        return data
    except (OSError, json.JSONDecodeError):
        return _empty()


def save(path: Path, graph: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def node_id(kind: str, value: Any) -> str:
    normalized = " ".join(str(value or "").strip().lower().split())
    return f"{kind}:{normalized}"[:500]


def upsert_node(graph: dict[str, Any], kind: str, value: Any, **attrs: Any) -> str:
    nid = node_id(kind, value)
    if not nid or nid.endswith(":"):
        return ""
    nodes = graph.setdefault("nodes", {})
    current = nodes.setdefault(nid, {"id": nid, "kind": kind, "value": str(value), "observations": 0})
    current["observations"] = int(current.get("observations", 0)) + 1
    current["lastSeen"] = now_iso()
    for key, val in attrs.items():
        if val not in (None, "", [], {}):
            current[key] = val
    return nid


def add_edge(graph: dict[str, Any], source: str, relation: str, target: str, **attrs: Any) -> None:
    if not source or not target:
        return
    edges = graph.setdefault("edges", [])
    for edge in reversed(edges[-1000:]):
        if edge.get("source") == source and edge.get("relation") == relation and edge.get("target") == target:
            edge["observations"] = int(edge.get("observations", 0)) + 1
            edge["lastSeen"] = now_iso()
            return
    edges.append({"source": source, "relation": relation, "target": target, "observations": 1, "lastSeen": now_iso(), **attrs})


def observe_feed(feed: dict[str, Any], path: Path) -> dict[str, Any]:
    graph = load(path)
    events = feed.get("events") or []
    for event in events:
        if not isinstance(event, dict):
            continue
        eid = upsert_node(graph, "event", event.get("id"), title=event.get("title"), startUtc=event.get("startUtc"), phase=event.get("intelligencePhase"))
        league = upsert_node(graph, "league", event.get("league"))
        sport = upsert_node(graph, "sport", event.get("sport"))
        home = upsert_node(graph, "team", event.get("home"))
        away = upsert_node(graph, "team", event.get("away"))
        provider = upsert_node(graph, "provider", event.get("provider") or event.get("sourceProvider") or "unknown")
        network = upsert_node(graph, "network", event.get("broadcast"))
        for relation, target in (("belongs_to", league), ("sport", sport), ("home_team", home), ("away_team", away), ("provided_by", provider), ("carried_by", network)):
            add_edge(graph, eid, relation, target)
        if event.get("sourceUrl") or event.get("youtubeVideoId"):
            source = upsert_node(graph, "source", event.get("sourceUrl") or event.get("youtubeVideoId"), sourceType="playable_metadata")
            add_edge(graph, eid, "has_source", source)

    # Keep the graph bounded and deterministic.
    nodes = graph.get("nodes", {})
    if len(nodes) > MAX_NODES:
        keep_ids = {k for k, _ in sorted(nodes.items(), key=lambda kv: kv[1].get("lastSeen", ""), reverse=True)[:MAX_NODES]}
        graph["nodes"] = {k: v for k, v in nodes.items() if k in keep_ids}
    valid = set(graph["nodes"])
    edges = [e for e in graph.get("edges", []) if e.get("source") in valid and e.get("target") in valid]
    graph["edges"] = edges[-MAX_EDGES:]
    graph["updatedAt"] = now_iso()
    graph["stats"] = {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "eventsObserved": len(events)}
    save(path, graph)
    return graph["stats"]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("feed")
    parser.add_argument("--graph", default="data/sports_knowledge_graph.json")
    args = parser.parse_args()
    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    print(json.dumps(observe_feed(feed, Path(args.graph)), indent=2))


if __name__ == "__main__":
    main()
