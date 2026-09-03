package com.xsportsx.app

import android.content.Context
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

    /** Canonical O(1)-style event lookup rebuilt atomically with engine state. */
    val eventIndex = EventIndex()

    @Volatile private var started = false
    private var scheduleJob: Job? = null
    private var liveJob: Job? = null
    @Volatile private var appContext: Context? = null

    /** Start the shared schedule engine and enable background stream prewarming. */
    fun start(context: Context? = null) {
        context?.let { appContext = it.applicationContext }
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
            .onSuccess { events -> publish(events, mutableState.value.liveEvents) }
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
            .onSuccess { live -> publish(mutableState.value.events, live) }
            .onFailure { failure ->
                val current = mutableState.value
                if (current.liveEvents.isEmpty()) {
                    mutableState.value = current.copy(error = failure.message ?: "Live feed unavailable")
                }
            }
    }

    /** Publish one canonical event collection and rebuild its identity index together. */
    private fun publish(base: List<SportsEvent>, live: List<SportsEvent>) {
        val merged = mergeLive(base, live)
            .map { it.copy(id = EventIdentity.id(it)) }
        val canonicalLive = merged.filter { it.isLive }
        eventIndex.rebuild(merged)
        val current = mutableState.value
        mutableState.value = current.copy(
            events = merged,
            liveEvents = canonicalLive,
            loading = false,
            refreshing = false,
            lastUpdatedMs = System.currentTimeMillis(),
            error = null
        )

        // Fire-and-forget: schedule refreshes never wait on stream discovery.
        appContext?.let { StreamPrewarmCoordinator.onSchedulePublished(it, merged) }
    }

    /** Overlay the hot live feed onto the warm schedule without duplicating events. */
    private fun mergeLive(base: List<SportsEvent>, live: List<SportsEvent>): List<SportsEvent> {
        if (live.isEmpty()) return base
        val liveById = live.filter { it.id.isNotBlank() }.associateBy { it.id }
        val liveByKey = live.associateBy(EventIdentity::key)
        val seenLive = HashSet<String>()

        val merged = base.map { event ->
            val replacement = liveById[event.id]?.also { seenLive.add(EventIdentity.id(it)) }
                ?: liveByKey[EventIdentity.key(event)]?.also { seenLive.add(EventIdentity.id(it)) }
            replacement ?: event
        }.toMutableList()

        live.forEach { event ->
            val alreadyPresent = merged.any {
                if (event.id.isNotBlank() && it.id.isNotBlank()) it.id == event.id
                else EventIdentity.key(it) == EventIdentity.key(event)
            }
            if (!alreadyPresent && seenLive.add(EventIdentity.id(event))) merged.add(event)
        }

        return merged.sortedWith(compareByDescending<SportsEvent> { it.isLive }.thenBy { it.startUtc })
    }
}
