package com.xsportsx.app

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Single runtime schedule engine shared by Mobile and TV.
 *
 * Schedule data is warm state; live state is hot state. UI code consumes this
 * engine instead of creating one-shot schedule requests of its own.
 */
object ScheduleEngine {
    private const val LIVE_REFRESH_MS = 10_000L
    private const val SCHEDULE_REFRESH_MS = 5 * 60_000L

    data class State(
        val events: List<SportsEvent> = emptyList(),
        val liveEvents: List<SportsEvent> = emptyList(),
        val loading: Boolean = true,
        val refreshing: Boolean = false,
        val lastUpdatedMs: Long = 0L,
        val error: String? = null
    )

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutableState = MutableStateFlow(State())
    val state: StateFlow<State> = mutableState.asStateFlow()

    @Volatile private var started = false
    private var scheduleJob: Job? = null
    private var liveJob: Job? = null

    fun start() {
        if (started) return
        synchronized(this) {
            if (started) return
            started = true
            scheduleJob = scope.launch { scheduleLoop() }
            liveJob = scope.launch { liveLoop() }
        }
    }

    suspend fun refreshNow() {
        refreshSchedule(force = true)
        refreshLive(force = true)
    }

    private suspend fun scheduleLoop() {
        refreshSchedule(force = false)
        while (scope.isActive) {
            delay(SCHEDULE_REFRESH_MS)
            refreshSchedule(force = true)
        }
    }

    private suspend fun liveLoop() {
        refreshLive(force = true)
        while (scope.isActive) {
            delay(LIVE_REFRESH_MS)
            refreshLive(force = true)
        }
    }

    private suspend fun refreshSchedule(force: Boolean) {
        val before = mutableState.value
        mutableState.value = before.copy(
            loading = before.events.isEmpty(),
            refreshing = before.events.isNotEmpty(),
            error = null
        )

        runCatching { ScheduleSnapshotRepository.all(force) }
            .onSuccess { events ->
                val current = mutableState.value
                val merged = mergeLive(events, current.liveEvents)
                mutableState.value = current.copy(
                    events = merged,
                    loading = false,
                    refreshing = false,
                    lastUpdatedMs = System.currentTimeMillis(),
                    error = null
                )
            }
            .onFailure { failure ->
                val current = mutableState.value
                mutableState.value = current.copy(
                    loading = false,
                    refreshing = false,
                    error = if (current.events.isEmpty()) failure.message ?: "Schedule unavailable" else null
                )
            }
    }

    private suspend fun refreshLive(force: Boolean) {
        runCatching { ScheduleSnapshotRepository.live(force) }
            .onSuccess { live ->
                val current = mutableState.value
                mutableState.value = current.copy(
                    events = mergeLive(current.events, live),
                    liveEvents = live,
                    lastUpdatedMs = System.currentTimeMillis(),
                    error = if (current.events.isEmpty() && live.isEmpty()) current.error else null
                )
            }
            .onFailure { failure ->
                val current = mutableState.value
                if (current.liveEvents.isEmpty()) {
                    mutableState.value = current.copy(error = failure.message ?: "Live feed unavailable")
                }
            }
    }

    /** Overlay the hot live feed onto the warm schedule without duplicating events. */
    private fun mergeLive(base: List<SportsEvent>, live: List<SportsEvent>): List<SportsEvent> {
        if (live.isEmpty()) return base
        val liveById = live.filter { it.id.isNotBlank() }.associateBy { it.id }
        val liveByFallback = live.associateBy { fallbackKey(it) }
        val seenLive = HashSet<String>()

        val merged = base.map { event ->
            val replacement = liveById[event.id]?.also { seenLive.add(it.id) }
                ?: liveByFallback[fallbackKey(event)]?.also { seenLive.add(it.id) }
            replacement ?: event
        }.toMutableList()

        live.forEach { event ->
            val key = if (event.id.isNotBlank()) "id:${event.id}" else "key:${fallbackKey(event)}"
            val alreadyPresent = merged.any {
                if (event.id.isNotBlank() && it.id.isNotBlank()) it.id == event.id
                else fallbackKey(it) == fallbackKey(event)
            }
            if (!alreadyPresent && seenLive.add(key)) merged.add(event)
        }

        return merged.sortedWith(compareByDescending<SportsEvent> { it.isLive }.thenBy { it.startUtc })
    }

    private fun fallbackKey(event: SportsEvent): String = listOf(
        event.league.trim().uppercase(),
        event.home.trim().uppercase(),
        event.away.trim().uppercase(),
        event.startUtc.take(16)
    ).joinToString("|")
}
