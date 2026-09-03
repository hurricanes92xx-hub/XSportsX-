package com.xsportsx.app

import java.time.Instant

enum class EventLifecycle {
    LIVE_CONFIRMED,
    LIVE_INFERRED,
    PREGAME,
    SCHEDULED,
    FINAL,
    STALE_UNKNOWN
}

/** Conservative lifecycle resolver: stale LIVE signals cannot keep an event live forever. */
object EventLifecycleResolver {
    private const val START_GRACE_MS = 5L * 60_000L
    private const val INFERRED_LIVE_MS = 20L * 60_000L

    fun resolve(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): EventLifecycle {
        if (isTerminal(event)) return EventLifecycle.FINAL

        val startMillis = runCatching { Instant.parse(event.startUtc).toEpochMilli() }.getOrNull()
            ?: return EventLifecycle.STALE_UNKNOWN
        val elapsed = nowMillis - startMillis

        if (elapsed < -START_GRACE_MS) return EventLifecycle.SCHEDULED

        if (hasLiveSignal(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) {
                EventLifecycle.LIVE_CONFIRMED
            } else {
                EventLifecycle.STALE_UNKNOWN
            }
        }

        // Time-only inference is deliberately short. It is only a bootstrap fallback;
        // after this window an event without a live signal is not shown as LIVE.
        if (elapsed in 0..INFERRED_LIVE_MS) return EventLifecycle.LIVE_INFERRED
        if (elapsed < 0) return EventLifecycle.PREGAME
        return EventLifecycle.STALE_UNKNOWN
    }

    fun isLive(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean =
        when (resolve(event, nowMillis)) {
            EventLifecycle.LIVE_CONFIRMED, EventLifecycle.LIVE_INFERRED -> true
            else -> false
        }

    fun isTerminal(event: SportsEvent): Boolean {
        val status = "${event.status} ${event.state}".lowercase()
        return status.contains("final") ||
            status.contains("finished") ||
            status.contains("complete") ||
            status.contains("cancel") ||
            status.contains("postpon") ||
            status.contains("abandon") ||
            event.state.equals("post", true) ||
            event.state.equals("final", true)
    }

    private fun hasLiveSignal(event: SportsEvent): Boolean {
        val status = event.status.trim().lowercase()
        val state = event.state.trim().lowercase()
        return state == "in" || state == "live" ||
            status == "live" || status == "in progress" || status == "in-progress" ||
            status.contains("live") || status.contains("in progress")
    }

    private fun maxLiveDurationMs(event: SportsEvent): Long {
        val key = "${event.sport} ${event.league} ${event.title}".lowercase()
        val minutes = when {
            key.contains("soccer") -> 165L
            key.contains("volleyball") -> 180L
            key.contains("tennis") -> 6L * 60L
            key.contains("baseball") || key.contains("mlb") -> 6L * 60L
            key.contains("football") || key.contains("nfl") -> 4L * 60L
            key.contains("hockey") -> 4L * 60L
            key.contains("basketball") -> 3L * 60L
            key.contains("golf") -> 10L * 60L
            else -> 3L * 60L
        }
        return minutes * 60_000L
    }
}
