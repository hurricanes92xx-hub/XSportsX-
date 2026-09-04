"""Autonomous sports intelligence engine.

This is deliberately deterministic and evidence-driven rather than an LLM runtime.
It continuously reasons over schedule/live/source evidence, detects contradictions,
chooses the next probe, and produces an explainable decision for the publisher.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Mapping, Optional


class EventPhase(str, Enum):
    UNKNOWN = "UNKNOWN"
    UPCOMING = "UPCOMING"
    PREGAME = "PREGAME"
    LIVE = "LIVE"
    STALE = "STALE"
    FINAL = "FINAL"


@dataclass(frozen=True)
class Evidence:
    kind: str
    value: str
    confidence: float = 0.5
    observed_at: Optional[datetime] = None
    provider: str = ""


@dataclass(frozen=True)
class IntelligenceDecision:
    phase: EventPhase
    confidence: float
    next_action: str
    source_priority: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass
class EventMemory:
    """Small persistent-friendly memory record for learning provider behavior."""
    observations: int = 0
    live_confirmations: int = 0
    false_live_signals: int = 0
    source_successes: int = 0
    source_failures: int = 0
    last_phase: EventPhase = EventPhase.UNKNOWN
    last_confidence: float = 0.0

    @property
    def provider_reliability(self) -> float:
        total = self.live_confirmations + self.false_live_signals
        return self.live_confirmations / total if total else 0.5


class SportsIntelligence:
    """Evidence fusion + self-healing decision layer for live/upcoming sports."""

    PREGAME_MS = 45 * 60 * 1000
    UPCOMING_MS = 7 * 24 * 60 * 60 * 1000

    def decide(
        self,
        *,
        start_utc: datetime,
        sport: str,
        status: str = "",
        state: str = "",
        score_present: bool = False,
        clock_present: bool = False,
        broadcast_present: bool = False,
        source_healthy: bool = False,
        evidence: Iterable[Evidence] = (),
        memory: Optional[EventMemory] = None,
        now: Optional[datetime] = None,
    ) -> IntelligenceDecision:
        now = now or datetime.now(timezone.utc)
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        elapsed = (now - start_utc).total_seconds() * 1000
        text = f"{status} {state}".lower()
        ev = list(evidence)
        reasons: list[str] = []

        terminal = any(x in text for x in ("final", "finished", "complete", "cancel", "postpon", "abandon"))
        if terminal:
            return IntelligenceDecision(EventPhase.FINAL, 0.99, "archive", reasons=("terminal provider state",))

        explicit_live = any(x in text for x in ("live", "in progress", "in-progress"))
        independent_live = score_present or clock_present or any(
            e.kind in {"score", "clock", "period", "live_feed"} and e.confidence >= 0.65 for e in ev
        )

        if explicit_live and elapsed <= self._max_live_ms(sport):
            confidence = 0.92
            if independent_live:
                confidence += 0.06
            if memory:
                confidence = min(0.99, confidence * (0.85 + 0.15 * memory.provider_reliability))
            reasons.append("explicit live state")
            if independent_live:
                reasons.append("independent live evidence agrees")
            return IntelligenceDecision(EventPhase.LIVE, min(confidence, 0.99), "resolve_or_refresh_source", self._source_priority(source_healthy), tuple(reasons))

        if independent_live and elapsed >= -5 * 60 * 1000 and elapsed <= self._max_live_ms(sport):
            reasons.append("live telemetry detected without trusted live flag")
            return IntelligenceDecision(EventPhase.LIVE, 0.84, "probe_live_state_and_source", self._source_priority(source_healthy), tuple(reasons))

        if elapsed < 0:
            if elapsed >= -self.PREGAME_MS:
                reasons.append("event is inside adaptive pregame window")
                action = "warm_source" if source_healthy else "discover_source"
                return IntelligenceDecision(EventPhase.PREGAME, 0.94, action, self._source_priority(source_healthy), tuple(reasons))
            if elapsed >= -self.UPCOMING_MS:
                reasons.append("future event within seven-day intelligence horizon")
                return IntelligenceDecision(EventPhase.UPCOMING, 0.91, "refresh_schedule_and_preflight", self._source_priority(source_healthy), tuple(reasons))
            return IntelligenceDecision(EventPhase.UPCOMING, 0.75, "defer", (), ("outside active intelligence horizon",))

        # A missing live signal after the expected duration is stale, not live.
        reasons.append("start time passed without sufficient live evidence")
        action = "refresh_live_evidence" if elapsed <= self._max_live_ms(sport) else "reconcile_or_archive"
        return IntelligenceDecision(EventPhase.STALE, 0.88, action, self._source_priority(source_healthy), tuple(reasons))

    @staticmethod
    def _source_priority(source_healthy: bool) -> tuple[str, ...]:
        if source_healthy:
            return ("cached-healthy", "authorized-xtream", "known-public", "official-broadcaster")
        return ("authorized-xtream", "known-public", "official-broadcaster", "discovery")

    @staticmethod
    def _max_live_ms(sport: str) -> int:
        key = sport.lower()
        minutes = {
            "soccer": 165, "football": 240, "basketball": 180,
            "hockey": 240, "baseball": 360, "tennis": 360,
            "volleyball": 180, "golf": 600, "racing": 480,
            "nascar": 480, "f1": 240, "mma": 240,
        }
        for name, value in minutes.items():
            if name in key:
                return value * 60 * 1000
        return 180 * 60 * 1000


def reconcile_events(events: Iterable[Mapping], now: Optional[datetime] = None) -> list[dict]:
    """Attach an explainable intelligence decision to canonical event dictionaries."""
    engine = SportsIntelligence()
    output: list[dict] = []
    for raw in events:
        try:
            start = datetime.fromisoformat(str(raw["startUtc"]).replace("Z", "+00:00"))
            decision = engine.decide(
                start_utc=start,
                sport=str(raw.get("sport", "")),
                status=str(raw.get("status", "")),
                state=str(raw.get("state", "")),
                score_present=bool(raw.get("score") or raw.get("homeScore") is not None or raw.get("awayScore") is not None),
                clock_present=bool(raw.get("clock") or raw.get("period")),
                broadcast_present=bool(raw.get("broadcast")),
                source_healthy=bool(raw.get("sourceHealthy")),
            )
            item = dict(raw)
            item["intelligencePhase"] = decision.phase.value
            item["intelligenceConfidence"] = round(decision.confidence, 3)
            item["intelligenceAction"] = decision.next_action
            item["intelligenceReasons"] = list(decision.reasons)
            output.append(item)
        except Exception:
            item = dict(raw)
            item["intelligencePhase"] = EventPhase.UNKNOWN.value
            item["intelligenceConfidence"] = 0.0
            item["intelligenceAction"] = "validate_event"
            output.append(item)
    return output
