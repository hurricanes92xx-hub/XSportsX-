# Adaptive Provider Discovery

XSportsX now has a conservative Google-backed discovery layer for schedule gaps.

## Flow

`healthy providers -> gap detection -> Google discovery -> candidate probe -> schema/event validation -> identity merge -> repeated observation -> promotion -> provider matrix`

Google is not used on every event. Discovery runs only for leagues that remain unresolved after the configured provider matrix and cache recovery have been exhausted.

## Google surfaces

1. Google Programmable Search JSON API when `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID` are configured.
2. Google News RSS as a no-key fallback discovery signal.

The CI workflow supplies the optional credentials without putting them in the Android application.

## Learning / safety

- Candidate endpoints are persisted in `data/provider_knowledge.json`.
- HTTP probing is bounded by size and timeout limits.
- Only HTTP/HTTPS endpoints are accepted.
- Search results do not become providers automatically.
- A candidate must produce parseable event data and then pass repeated observations before promotion.
- Reliability and coverage are recorded per candidate.
- Promoted candidates can be re-probed on later refreshes and lose value when they stop returning events.
- Existing authoritative providers continue to outrank discovered providers.
- User-authorized Xtream remains the Tier-0 source for actual channel/source resolution.
- This layer is for schedule/provider discovery, not for finding unauthorized streams.

## Runtime contract

`refresh_schedules.py` now routes through `refresh_with_discovery.py`.

The canonical feed exposes:

- `providerDiscovery.discoveredCandidates`
- `providerDiscovery.promotedProviders`
- `providerDiscovery.fallbackAttempts`
- `discoveryCount`
- `discoveredProviders`
- `promotedProviders`

This makes discovery observable without changing the Android app's core schedule contract.
