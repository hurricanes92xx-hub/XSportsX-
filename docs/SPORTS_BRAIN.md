# XSportsX Sports Brain

The Sports Brain is the deterministic reasoning layer above the canonical provider matrix. It is designed to improve schedule and LIVE truth without replacing authoritative providers or the user's authorized Xtream source.

## Closed loop

`OBSERVE -> REASON -> ACT -> VERIFY -> LEARN`

Each refresh analyzes canonical events, fuses provider state with timing and available score/clock/source evidence, assigns an explainable phase/confidence/action, and stores bounded memory of event and provider behavior.

## Schedule protection

Adaptive discovery remains responsible for filling provider gaps. The Brain records the resulting evidence and can identify suspicious empty/stale situations instead of treating every provider failure as a genuinely empty schedule.

## LIVE protection

The Android lifecycle resolver now accepts high-confidence Brain LIVE evidence as an additional signal. It still rejects terminal events and enforces sport-aware maximum durations, so a stale Brain decision cannot keep an event LIVE forever.

## Learning memory

`data/sports_brain_memory.json` stores compact, non-secret observations. It contains no Xtream credentials. Event memory is bounded to 10,000 recent records.

Provider memory tracks observations, LIVE/stale classifications, and source presence. This is intended to become a future input to provider ranking rather than a hardcoded provider preference.

## Safety

The Brain does not execute arbitrary discovered instructions and does not search for unauthorized streams. Discovery is limited to schedule/evidence sources and legitimate source metadata; authorized Xtream remains Tier 0 for the user's own source resolution.
