package com.xsportsx.app

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.Instant
import java.time.temporal.ChronoUnit

/** Single canonical schedule snapshot shared by Mobile and TV. */
object ScheduleSnapshotRepository {
    private const val SNAPSHOT_TTL_MS = 5 * 60_000L
    private const val LIVE_TTL_MS = 10_000L
    private const val UI_DAYS = 3
    private const val SNAPSHOT_DAYS = 7

    private val snapshotMutex = Mutex()
    private val liveMutex = Mutex()
    @Volatile private var snapshotCache: CachedEvents? = null
    @Volatile private var liveCache: CachedEvents? = null

    private data class CachedEvents(val events: List<SportsEvent>, val loadedAtMs: Long)

    suspend fun all(force: Boolean = false): List<SportsEvent> {
        val cached = snapshotCache
        if (!force && cached != null && age(cached) < SNAPSHOT_TTL_MS) return cached.events

        return snapshotMutex.withLock {
            val again = snapshotCache
            if (!force && again != null && age(again) < SNAPSHOT_TTL_MS) return@withLock again.events

            val fresh = runCatching {
                CanonicalScheduleProvider.load(null, SNAPSHOT_DAYS)
            }.getOrDefault(emptyList())
            val normalized = normalize(fresh)

            if (normalized.isNotEmpty()) {
                snapshotCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else {
                // Never erase a good schedule because the feed is temporarily unavailable.
                again?.events.orEmpty()
            }
        }
    }

    suspend fun upcoming(league: String? = null, force: Boolean = false): List<SportsEvent> {
        val canonical = league?.let(SportsScheduleService::canonicalLeagueFor)
        val now = Instant.now()
        val cutoff = now.plus(UI_DAYS.toLong(), ChronoUnit.DAYS)

        return all(force).asSequence()
            .filter { !it.isLive }
            .filter { event -> canonical == null || SportsScheduleService.canonicalLeagueFor(event.league) == canonical }
            .filter { event ->
                val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
                val localDate = start.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val today = now.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val dateOnly = event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
                val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(UI_DAYS.toLong()))
                dateOnlyInWindow || (!start.isBefore(now.minus(10, ChronoUnit.MINUTES)) && start.isBefore(cutoff))
            }
            .sortedBy { it.startUtc }
            .toList()
    }

    /** Near-real-time live path. A forced refresh always goes to the canonical feed. */
    suspend fun live(force: Boolean = false): List<SportsEvent> {
        val cached = liveCache
        if (!force && cached != null && age(cached) < LIVE_TTL_MS) return cached.events

        return liveMutex.withLock {
            val again = liveCache
            if (!force && again != null && age(again) < LIVE_TTL_MS) return@withLock again.events

            val fresh = runCatching { CanonicalScheduleProvider.load(null, 1) }
                .getOrDefault(emptyList())
            val normalized = normalize(fresh).filter { it.isLive }
            if (normalized.isNotEmpty() || fresh.isNotEmpty()) {
                liveCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else {
                again?.events.orEmpty()
            }
        }
    }

    fun clear() {
        snapshotCache = null
        liveCache = null
    }

    private fun age(cache: CachedEvents): Long = System.currentTimeMillis() - cache.loadedAtMs

    private fun normalize(events: List<SportsEvent>): List<SportsEvent> {
        val seen = LinkedHashSet<String>()
        return events
            .map { it.copy(league = SportsScheduleService.canonicalLeagueFor(it.league)) }
            .filter { seen.add(eventKey(it)) }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    /** Stable matchup key prevents duplicate live cards when the same game arrives with different feed IDs. */
    private fun eventKey(event: SportsEvent): String {
        fun clean(value: String): String = value.lowercase()
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
            .replace(Regex("\\s+"), " ")
        val teams = listOf(clean(event.away), clean(event.home)).sorted()
        val matchup = if (teams.any { it.isNotBlank() }) teams.joinToString("|") else clean(event.title)
        val start = event.startUtc.take(16)
        return "${clean(event.league)}|$matchup|$start"
    }
}
