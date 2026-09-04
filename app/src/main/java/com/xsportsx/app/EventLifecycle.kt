package com.xsportsx.app

import java.time.Instant

/** Canonical lifecycle states used by schedule, matching and playback. */
enum class EventLifecycle {
    LIVE_CONFIRMED,
    LIVE_INFERRED,
    PREGAME,
    SCHEDULED,
    FINAL,
    STALE_UNKNOWN
}

/**
 * Self-sufficient event intelligence.
 *
 * It combines explicit provider state, clock position, event metadata and sport-aware
 * timing instead of treating "start time has passed" as proof of LIVE.  This lets the
 * client remain useful when a provider is late, briefly stale, or omits a live flag.
 */
object EventLifecycleResolver {
    private const val START_GRACE_MS = 5L * 60_000L
    private const val INFERRED_LIVE_MS = 20L * 60_000L

    fun resolve(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): EventLifecycle {
        if (isTerminal(event)) return EventLifecycle.FINAL

        val startMillis = parseStart(event) ?: return EventLifecycle.STALE_UNKNOWN
        val untilStart = startMillis - nowMillis
        val elapsed = nowMillis - startMillis

        if (untilStart > startGraceMs(event)) return EventLifecycle.SCHEDULED
        if (hasStrongLiveSignal(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) {
                EventLifecycle.LIVE_CONFIRMED
            } else {
                EventLifecycle.STALE_UNKNOWN
            }
        }

        // Some feeds omit state while still exposing score/period/clock/broadcast data.
        if (hasSoftLiveEvidence(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) {
                EventLifecycle.LIVE_INFERRED
            } else EventLifecycle.STALE_UNKNOWN
        }

        // Small, sport-aware bootstrap window for feeds that publish the schedule before
        // their live-state endpoint. This is never allowed to keep an event live forever.
        if (elapsed in 0..inferredWindowMs(event)) return EventLifecycle.LIVE_INFERRED
        if (untilStart > 0) return EventLifecycle.PREGAME
        return EventLifecycle.STALE_UNKNOWN
    }

    fun isLive(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean =
        resolve(event, nowMillis) in setOf(EventLifecycle.LIVE_CONFIRMED, EventLifecycle.LIVE_INFERRED)

    fun isTerminal(event: SportsEvent): Boolean {
        val status = "${event.status} ${event.state}".lowercase()
        return status.contains("final") || status.contains("finished") ||
            status.contains("complete") || status.contains("cancel") ||
            status.contains("postpon") || status.contains("abandon") ||
            event.state.equals("post", true) || event.state.equals("final", true)
    }

    /** True only for provider states that are explicit enough to call LIVE confidently. */
    private fun hasStrongLiveSignal(event: SportsEvent): Boolean {
        val status = event.status.trim().lowercase()
        val state = event.state.trim().lowercase()
        return state == "in" || state == "live" || state == "inprogress" ||
            status == "live" || status == "in progress" || status == "in-progress" ||
            status == "inprogress" || status.contains("live") || status.contains("in progress")
    }

    /**
     * Soft evidence catches feeds where the status field is stale/blank but the event has
     * live-only metadata. It deliberately does not use a broadcast name alone as evidence.
     */
    private fun hasSoftLiveEvidence(event: SportsEvent): Boolean {
        val text = "${event.status} ${event.state}".lowercase()
        val clockLike = Regex("\\b\\d{1,2}[:.]\\d{2}\\b").containsMatchIn(text)
        val periodLike = text.contains("period") || text.contains("quarter") ||
            text.contains("inning") || text.contains("set") || text.contains("round") ||
            text.contains("half") || text.contains("overtime")
        val scoreLike = Regex("\\b\\d+\\s*[-:]\\s*\\d+\\b").containsMatchIn(text)
        return clockLike || periodLike || scoreLike
    }

    /** Upcoming is intentionally broader than the old fixed 3-day UI horizon. */
    fun isUpcoming(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean {
        if (isTerminal(event)) return false
        val start = parseStart(event) ?: return false
        val delta = start - nowMillis
        return delta > 0 && delta <= upcomingWindowMs(event) &&
            resolve(event, nowMillis) in setOf(EventLifecycle.SCHEDULED, EventLifecycle.PREGAME)
    }

    /** How soon an event should enter the PREGAME state. */
    fun isPregame(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = parseStart(event) ?: return false
        val delta = start - nowMillis
        return delta in 0..pregameWindowMs(event) && resolve(event, nowMillis) == EventLifecycle.PREGAME
    }

    fun confidence(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Int {
        val start = parseStart(event) ?: return 0
        val elapsed = nowMillis - start
        if (isTerminal(event)) return 100
        if (hasStrongLiveSignal(event)) return if (elapsed <= maxLiveDurationMs(event)) 98 else 10
        if (hasSoftLiveEvidence(event)) return if (elapsed <= maxLiveDurationMs(event)) 82 else 12
        if (elapsed in 0..inferredWindowMs(event)) return 62
        if (start > nowMillis && start - nowMillis <= pregameWindowMs(event)) return 92
        if (start > nowMillis) return 80
        return 25
    }

    private fun parseStart(event: SportsEvent): Long? =
        runCatching { Instant.parse(event.startUtc).toEpochMilli() }.getOrNull()

    private fun sportKey(event: SportsEvent): String =
        "${event.sport} ${event.league} ${event.title}".lowercase()

    private fun pregameWindowMs(event: SportsEvent): Long {
        val k = sportKey(event)
        val minutes = when {
            k.contains("football") || k.contains("nfl") || k.contains("cfl") -> 60L
            k.contains("baseball") || k.contains("mlb") -> 45L
            k.contains("hockey") || k.contains("nhl") -> 45L
            k.contains("basketball") || k.contains("nba") -> 30L
            k.contains("soccer") || k.contains("mls") || k.contains("epl") -> 45L
            k.contains("golf") -> 90L
            k.contains("tennis") -> 30L
            else -> 30L
        }
        return minutes * 60_000L
    }

    private fun upcomingWindowMs(event: SportsEvent): Long {
        val k = sportKey(event)
        val days = when {
            k.contains("golf") || k.contains("tennis") -> 7L
            k.contains("f1") || k.contains("formula") || k.contains("nascar") -> 14L
            k.contains("football") || k.contains("basketball") || k.contains("hockey") || k.contains("baseball") -> 7L
            else -> 7L
        }
        return days * 24L * 60L * 60L * 1000L
    }

    private fun startGraceMs(event: SportsEvent): Long = when {
        sportKey(event).contains("soccer") -> 10L * 60_000L
        sportKey(event).contains("golf") -> 20L * 60_000L
        else -> START_GRACE_MS
    }

    private fun inferredWindowMs(event: SportsEvent): Long = when {
        sportKey(event).contains("soccer") -> 15L * 60_000L
        sportKey(event).contains("tennis") -> 30L * 60_000L
        sportKey(event).contains("baseball") -> 25L * 60_000L
        else -> INFERRED_LIVE_MS
    }

    private fun maxLiveDurationMs(event: SportsEvent): Long {
        val key = sportKey(event)
        val minutes = when {
            key.contains("soccer") -> 165L
            key.contains("volleyball") -> 180L
            key.contains("tennis") -> 6L * 60L
            key.contains("baseball") || key.contains("mlb") -> 6L * 60L
            key.contains("football") || key.contains("nfl") || key.contains("cfl") -> 4L * 60L
            key.contains("hockey") -> 4L * 60L
            key.contains("basketball") -> 3L * 60L
            key.contains("golf") -> 10L * 60L
            key.contains("racing") || key.contains("nascar") || key.contains("f1") -> 6L * 60L
            else -> 3L * 60L
        }
        return minutes * 60_000L
    }
}
