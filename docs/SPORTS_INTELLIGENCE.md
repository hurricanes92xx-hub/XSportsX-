# XSportsX Sports Intelligence

XSportsX now treats event state as an evidence-fusion problem rather than a single provider field.

## Intelligence loop

`OBSERVE -> NORMALIZE -> CORRELATE -> SCORE -> DECIDE -> ACT -> VERIFY -> LEARN`

The intelligence layer evaluates schedule timing, provider state, score/clock/period telemetry, source health, broadcast metadata, and historical provider reliability.

## Decisions

- `UPCOMING`: future event inside the active intelligence horizon.
- `PREGAME`: event is approaching; source discovery/prewarming can begin.
- `LIVE`: explicit live state or sufficiently strong independent live telemetry.
- `STALE`: expected live window passed without adequate evidence.
- `FINAL`: terminal provider evidence.
- `UNKNOWN`: malformed or insufficient event data.

## Self-healing behavior

A weak or contradictory signal does not immediately overwrite the canonical state. The engine chooses the next action: refresh live evidence, preflight a source, discover a source, resolve a source, reconcile, or archive.

Schedule discovery and source discovery remain separate. An event can be known without having a playable source, and a source can be healthy without proving an event is live.

## Learning

`EventMemory` records observations, live confirmations, false live signals, source successes, and source failures. Provider reliability influences confidence but never overrides authoritative terminal evidence.

## Guardrails

The intelligence layer is deterministic, explainable, and bounded. It does not invent events or streams. Candidate providers and sources must still pass schema validation, identity matching, freshness checks, health checks, and existing authorization/legal-source rules before promotion.
