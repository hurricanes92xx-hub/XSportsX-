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
 * Sport-aware lifecycle resolver. Explicit provider/official state always wins;
 * timing inference is only a fallback and uses the sport's expected cadence.
 */
object EventLifecycleResolver {
    private const val START_GRACE_MS = 5L * 60_000L

    private data class SportProfile(
        val pregameMinutes: Long,
        val inferredMinutes: Long,
        val maxLiveMinutes: Long,
        val startGraceMinutes: Long = 5L
    )

    private val DEFAULT = SportProfile(30, 30, 180)
    private val PROFILES = mapOf(
        "soccer" to SportProfile(45, 30, 180, 10),
        "football" to SportProfile(60, 60, 300),
        "baseball" to SportProfile(45, 45, 240),
        "hockey" to SportProfile(45, 45, 240),
        "basketball" to SportProfile(30, 35, 180),
        "volleyball" to SportProfile(30, 45, 210),
        "tennis" to SportProfile(30, 60, 360),
        "golf" to SportProfile(90, 90, 600, 20),
        "racing" to SportProfile(60, 90, 360),
        "mma" to SportProfile(60, 360, 360),
        "boxing" to SportProfile(60, 240, 360),
        "wrestling" to SportProfile(60, 240, 300)
    )

    fun resolve(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): EventLifecycle {
        if (isTerminal(event)) return EventLifecycle.FINAL
        val startMillis = parseStart(event) ?: return EventLifecycle.STALE_UNKNOWN
        val untilStart = startMillis - nowMillis
        val elapsed = nowMillis - startMillis
        if (untilStart > startGraceMs(event)) return EventLifecycle.SCHEDULED

        // Explicit provider/brain evidence is authoritative over inferred timing.
        if (hasStrongLiveSignal(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) EventLifecycle.LIVE_CONFIRMED else EventLifecycle.STALE_UNKNOWN
        }
        if (hasBrainLiveEvidence(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) EventLifecycle.LIVE_CONFIRMED else EventLifecycle.STALE_UNKNOWN
        }
        if (hasSoftLiveEvidence(event)) {
            return if (elapsed <= maxLiveDurationMs(event)) EventLifecycle.LIVE_INFERRED else EventLifecycle.STALE_UNKNOWN
        }

        // No explicit state: give each sport a realistic bootstrap window.
        if (elapsed in 0..inferredWindowMs(event)) return EventLifecycle.LIVE_INFERRED
        if (untilStart > 0) return EventLifecycle.PREGAME
        return EventLifecycle.STALE_UNKNOWN
    }

    fun isLive(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean =
        resolve(event, nowMillis) in setOf(EventLifecycle.LIVE_CONFIRMED, EventLifecycle.LIVE_INFERRED)

    fun isTerminal(event: SportsEvent): Boolean {
        val status = "${event.status} ${event.state}".lowercase()
        return status.contains("final") || status.contains("finished") || status.contains("complete") ||
            status.contains("cancel") || status.contains("postpon") || status.contains("abandon") ||
            event.state.equals("post", true) || event.state.equals("final", true)
    }

    private fun hasStrongLiveSignal(event: SportsEvent): Boolean {
        val status = event.status.trim().lowercase()
        val state = event.state.trim().lowercase()
        return state == "in" || state == "live" || state == "inprogress" ||
            state == "in_progress" || status == "live" || status == "in progress" ||
            status == "in-progress" || status == "inprogress" || status == "in_progress" ||
            status.contains("live") || status.contains("in progress") || status.contains("in-progress")
    }

    private fun hasBrainLiveEvidence(event: SportsEvent): Boolean =
        event.intelligencePhase.equals("LIVE", true) && event.intelligenceConfidence >= 0.90

    private fun hasSoftLiveEvidence(event: SportsEvent): Boolean {
        val text = "${event.status} ${event.state}".lowercase()
        val clockLike = Regex("\\b\\d{1,2}[:.]\\d{2}\\b").containsMatchIn(text)
        val periodLike = text.contains("period") || text.contains("quarter") || text.contains("inning") ||
            text.contains("set") || text.contains("round") || text.contains("half") || text.contains("overtime")
        val scoreLike = Regex("\\b\\d+\\s*[-:]\\s*\\d+\\b").containsMatchIn(text)
        return clockLike || periodLike || scoreLike
    }

    fun isUpcoming(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean {
        if (isTerminal(event)) return false
        val start = parseStart(event) ?: return false
        val delta = start - nowMillis
        return delta > 0 && delta <= upcomingWindowMs(event) &&
            resolve(event, nowMillis) in setOf(EventLifecycle.SCHEDULED, EventLifecycle.PREGAME)
    }

    fun isPregame(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Boolean {
        if (isTerminal(event)) return false
        val start = parseStart(event) ?: return false
        val delta = start - nowMillis
        return delta in 0..pregameWindowMs(event) && resolve(event, nowMillis) == EventLifecycle.PREGAME
    }

    fun confidence(event: SportsEvent, nowMillis: Long = System.currentTimeMillis()): Int {
        val start = parseStart(event) ?: return 0
        val elapsed = nowMillis - start
        if (isTerminal(event)) return 100
        if (hasStrongLiveSignal(event)) return if (elapsed <= maxLiveDurationMs(event)) 98 else 10
        if (hasBrainLiveEvidence(event)) return if (elapsed <= maxLiveDurationMs(event)) (event.intelligenceConfidence * 100.0).toInt().coerceIn(1, 99) else 12
        if (hasSoftLiveEvidence(event)) return if (elapsed <= maxLiveDurationMs(event)) 82 else 12
        if (elapsed in 0..inferredWindowMs(event)) return 62
        if (start > nowMillis && start - nowMillis <= pregameWindowMs(event)) return 92
        if (start > nowMillis) return 80
        return 25
    }

    private fun parseStart(event: SportsEvent): Long? =
        runCatching { Instant.parse(event.startUtc).toEpochMilli() }.getOrNull()

    private fun profile(event: SportsEvent): SportProfile {
        val key = sportKey(event)
        return when {
            containsAny(key, "ufc", "mma") -> PROFILES.getValue("mma")
            containsAny(key, "boxing") -> PROFILES.getValue("boxing")
            containsAny(key, "wwe", "aew", "tna", "wrestling", "aaa wrestling") -> PROFILES.getValue("wrestling")
            containsAny(key, "f1", "formula 1", "nascar", "motogp", "imsa", "wec", "wrc", "racing") -> PROFILES.getValue("racing")
            containsAny(key, "soccer", "mls", "epl", "uefa", "fifa") -> PROFILES.getValue("soccer")
            containsAny(key, "nfl", "ncaa football", "college football", "cfl", "football") -> PROFILES.getValue("football")
            containsAny(key, "mlb", "baseball") -> PROFILES.getValue("baseball")
            containsAny(key, "nhl", "hockey") -> PROFILES.getValue("hockey")
            containsAny(key, "nba", "wnba", "ncaa basketball", "basketball") -> PROFILES.getValue("basketball")
            containsAny(key, "volleyball") -> PROFILES.getValue("volleyball")
            containsAny(key, "atp", "wta", "tennis") -> PROFILES.getValue("tennis")
            containsAny(key, "pga", "lpga", "golf") -> PROFILES.getValue("golf")
            else -> DEFAULT
        }
    }

    private fun sportKey(event: SportsEvent): String =
        "${event.sport} ${event.league} ${event.title}".lowercase()

    private fun containsAny(text: String, vararg values: String): Boolean =
        values.any { text.contains(it) }

    private fun pregameWindowMs(event: SportsEvent): Long = profile(event).pregameMinutes * 60_000L
    private fun inferredWindowMs(event: SportsEvent): Long = profile(event).inferredMinutes * 60_000L
    private fun maxLiveDurationMs(event: SportsEvent): Long = profile(event).maxLiveMinutes * 60_000L
    private fun startGraceMs(event: SportsEvent): Long = profile(event).startGraceMinutes * 60_000L
    private fun upcomingWindowMs(event: SportsEvent): Long = when {
        containsAny(sportKey(event), "golf", "tennis") -> 7L * 24L * 60L * 60L * 1000L
        containsAny(sportKey(event), "f1", "formula", "nascar", "motogp", "racing") -> 14L * 24L * 60L * 60L * 1000L
        else -> 7L * 24L * 60L * 60L * 1000L
    }
}
