package com.xsportsx.app

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Single client-side schedule snapshot for both Mobile and TV.
 *
 * The server-refreshed canonical feed is the source of truth. Screens never
 * fetch a league independently. A single bounded recovery pass is allowed
 * only when the shared snapshot/live view needs it, and its result is cached.
 */
object ScheduleSnapshotRepository {
    private const val SNAPSHOT_TTL_MS = 5 * 60_000L
    private const val LIVE_TTL_MS = 60_000L
    private const val UI_DAYS = 3
    private const val SNAPSHOT_DAYS = 30

    private val snapshotMutex = Mutex()
    private val liveMutex = Mutex()

    @Volatile private var snapshotCache: CachedEvents? = null
    @Volatile private var liveCache: CachedEvents? = null

    private data class CachedEvents(val events: List<SportsEvent>, val loadedAtMs: Long)

    suspend fun all(force: Boolean = false): List<SportsEvent> {
        val cached = snapshotCache
        if (!force && cached != null && System.currentTimeMillis() - cached.loadedAtMs < SNAPSHOT_TTL_MS) {
            return cached.events
        }

        return snapshotMutex.withLock {
            val again = snapshotCache
            if (!force && again != null && System.currentTimeMillis() - again.loadedAtMs < SNAPSHOT_TTL_MS) {
                return@withLock again.events
            }

            val canonical = runCatching { CanonicalScheduleProvider.load(null, SNAPSHOT_DAYS) }
                .getOrDefault(emptyList())
            val events = if (canonical.isNotEmpty()) {
                canonical
            } else {
                runCatching { SportsScheduleService.loadBackground() }
                    .getOrDefault(emptyList())
                    .ifEmpty { again?.events.orEmpty() }
            }

            val normalized = normalize(events)
            if (normalized.isNotEmpty()) {
                snapshotCache = CachedEvents(normalized, System.currentTimeMillis())
            }
            normalized.ifEmpty { again?.events.orEmpty() }
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
                val dateOnly = event.status.contains("upcoming", true) && event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
                val today = now.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val localDate = start.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(UI_DAYS.toLong()))
                dateOnlyInWindow || (!start.isBefore(now.minus(10, ChronoUnit.MINUTES)) && start.isBefore(cutoff))
            }
            .sortedBy { it.startUtc }
            .toList()
    }

    suspend fun live(force: Boolean = false): List<SportsEvent> {
        val base = all(force = false).filter { it.isLive }
        val cached = liveCache
        if (!force && cached != null && System.currentTimeMillis() - cached.loadedAtMs < LIVE_TTL_MS) {
            return mergeLive(base, cached.events)
        }

        return liveMutex.withLock {
            val again = liveCache
            if (!force && again != null && System.currentTimeMillis() - again.loadedAtMs < LIVE_TTL_MS) {
                return@withLock mergeLive(base, again.events)
            }

            // The canonical feed normally supplies live state. Recovery is one
            // shared all-league pass, not one network request per screen/league.
            val recovery = runCatching { SportsScheduleService.loadLiveRecovery() }
                .getOrDefault(emptyList())
            val merged = mergeLive(base, recovery)
            liveCache = CachedEvents(merged, System.currentTimeMillis())
            merged
        }
    }

    fun clear() {
        snapshotCache = null
        liveCache = null
    }

    private fun mergeLive(first: List<SportsEvent>, second: List<SportsEvent>): List<SportsEvent> =
        normalize(first + second)
            .filter { it.isLive }
            .sortedWith(compareBy<SportsEvent> { it.league.lowercase() }.thenBy { it.startUtc })

    private fun normalize(events: List<SportsEvent>): List<SportsEvent> =
        events.map { it.copy(league = SportsScheduleService.canonicalLeagueFor(it.league)) }
            .distinctBy { it.id.ifBlank { "${it.league}|${it.away}|${it.home}|${it.startUtc.take(16)}" } }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
}
