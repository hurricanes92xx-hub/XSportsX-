# XSportsX Autonomous Sports Agent

XSportsX now has a model-optional agent controller above the deterministic Sports Brain.

## Loop

`OBSERVE -> REASON -> PLAN -> ACT -> VERIFY -> LEARN`

- **Observe:** reads canonical events plus Brain evidence.
- **Reason:** uses the deterministic policy by default, or an optional OpenAI-compatible reasoning endpoint when configured.
- **Plan:** produces a strict JSON decision with action, confidence, reason, and evidence IDs.
- **Act:** executes only operations in the sports allowlist. No arbitrary shell commands, URLs, code, or discovered instructions are executable.
- **Verify:** action results are recorded as structured outcomes; the next refresh can use those observations.
- **Learn:** bounded agent memory and the persistent sports knowledge graph retain operational patterns.

## Model configuration

The model is intentionally optional so CI remains deterministic and the app does not depend on an external AI service. To enable model reasoning, configure these GitHub Actions values on the repository/organization:

- `SPORTS_AGENT_MODEL_URL` — **Actions Variable**, an OpenAI-compatible chat-completions endpoint.
- `SPORTS_AGENT_MODEL` — **Actions Variable**, the selected reasoning model name.
- `SPORTS_AGENT_MODEL_API_KEY` — **Actions Secret**, the API credential for that endpoint.

The schedule workflow passes those values only to the agent step. The API key is never written to the repository, feed, memory, or knowledge graph.

### Configuration examples

For an OpenAI-compatible gateway, use its chat-completions URL for `SPORTS_AGENT_MODEL_URL` and the exact deployed model identifier for `SPORTS_AGENT_MODEL`. The agent sends temperature `0` and requires JSON containing only an allowlisted action, confidence, reason, and evidence IDs.

If the endpoint is unavailable, malformed, or returns an unsafe action, the agent automatically falls back to the deterministic policy. The workflow reports `modelEnabled` so model-backed runs are distinguishable from fallback runs.

## Safe actions

The agent may request only sports-specific operations such as refreshing live evidence, discovering schedule providers, discovering legitimate source metadata, warming a known source, reconciling stale events, preflighting upcoming events, or deferring work.

The user's authorized Xtream source remains Tier 0 for their own source resolution. Xtream credentials are never written to agent memory or the knowledge graph.

## Knowledge graph

`data/sports_knowledge_graph.json` links events to teams, leagues, sports, providers, networks, and source metadata. It is bounded to prevent unbounded CI growth.

## Android contract

The canonical event already carries Brain advisory fields (`intelligencePhase`, `intelligenceConfidence`, `intelligenceAction`, and `intelligenceReasons`). The Android lifecycle resolver can use high-confidence Brain evidence while retaining local safety checks and sport-aware duration limits.

## What this enables next

This creates the control plane for a real sports AI: a future UI/voice layer can ask the agent for event explanations, “what is live?”, source-health decisions, matchup context, and recommendations without directly controlling providers. A stronger model can also be plugged in later without changing the provider matrix or Android playback architecture.
