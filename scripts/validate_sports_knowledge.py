#!/usr/bin/env python3
"""Validate the Sports Knowledge Brain before an AI audit can use it."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "sports_knowledge"
REQUIRED = ["sports.json","leagues.json","event_types.json","lifecycle_rules.json","broadcast_patterns.json","terminology.json","learned_lessons.json"]

def main() -> None:
    errors=[]; docs={}
    for name in REQUIRED:
        path=ROOT/name
        try:
            docs[name]=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{name}: unreadable: {exc}")
    if not errors:
        sports=docs["sports.json"].get("sports",{})
        leagues=docs["leagues.json"].get("leagues",{})
        profiles=docs["lifecycle_rules.json"].get("profiles",{})
        if len(sports) < 10: errors.append("sports.json: expected broad sport coverage")
        if len(leagues) < 10: errors.append("leagues.json: expected broad league coverage")
        for key in sports:
            if key not in profiles: errors.append(f"lifecycle_rules.json: missing profile for {key}")
        policy=docs["learned_lessons.json"].get("policy",{})
        if float(policy.get("minimumConfidence",0)) < 0.85: errors.append("learned_lessons.json: confidence gate too low")
        if int(policy.get("minimumIndependentEvidence",0)) < 2: errors.append("learned_lessons.json: evidence gate too low")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Sports Knowledge Brain OK: {len(docs['sports.json']['sports'])} sports, {len(docs['leagues.json']['leagues'])} leagues")

if __name__ == "__main__": main()
