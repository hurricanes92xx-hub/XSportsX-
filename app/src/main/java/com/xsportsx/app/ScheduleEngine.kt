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

/** Single runtime schedule engine shared by Mobile and TV. */
object ScheduleEngine {
    private const val LIVE_REFRESH_MS = 10_000L
    private const val SCHEDULE_REFRESH_MS = 5 * 60_000L
    data class State(val events: List<SportsEvent> = emptyList(), val liveEvents: List<SportsEvent> = emptyList(), val loading: Boolean = true, val refreshing: Boolean = false, val lastUpdatedMs: Long = 0L, val error: String? = null)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutableState = MutableStateFlow(State())
    val state: StateFlow<State> = mutableState.asStateFlow()
    val eventIndex = EventIndex()
    @Volatile private var started = false
    private var scheduleJob: Job? = null
    private var liveJob: Job? = null
    @Volatile private var appContext: Context? = null
    fun start(context: Context? = null) {
        context?.let { appContext = it.applicationContext }
        if (started) return
        synchronized(this) {
            if (started) return
            started = true
            // Force a network refresh immediately after install/startup so stale packaged/cache data is not presented as current.
            scheduleJob = scope.launch { scheduleLoop() }
            liveJob = scope.launch { liveLoop() }
        }
    }
    suspend fun refreshNow() { refreshSchedule(force = true); refreshLive(force = true) }
    private suspend fun scheduleLoop() { refreshSchedule(true); while (scope.isActive) { delay(SCHEDULE_REFRESH_MS); refreshSchedule(true) } }
    private suspend fun liveLoop() { refreshLive(true); while (scope.isActive) { delay(LIVE_REFRESH_MS); refreshLive(true) } }
    private suspend fun refreshSchedule(force: Boolean) {
        val before = mutableState.value
        mutableState.value = before.copy(loading = before.events.isEmpty(), refreshing = before.events.isNotEmpty(), error = null)
        runCatching { ScheduleSnapshotRepository.all(force) }.onSuccess { events -> publish(events, mutableState.value.liveEvents) }.onFailure { failure ->
            val current = mutableState.value
            mutableState.value = current.copy(loading = false, refreshing = false, error = if (current.events.isEmpty()) failure.message ?: "Schedule unavailable" else null)
        }
    }
    private suspend fun refreshLive(force: Boolean) {
        runCatching { ScheduleSnapshotRepository.live(force) }.onSuccess { live -> publish(mutableState.value.events, live) }.onFailure { failure ->
            val current = mutableState.value
            if (current.liveEvents.isEmpty()) mutableState.value = current.copy(error = failure.message ?: "Live feed unavailable")
        }
    }
    private fun publish(base: List<SportsEvent>, live: List<SportsEvent>) {
        val merged = mergeLive(base, live).map { it.copy(id = EventIdentity.id(it)) }.distinctBy(EventIdentity::key)
        val canonicalLive = merged.filter { it.isLive }
        eventIndex.rebuild(merged)
        val current = mutableState.value
        mutableState.value = current.copy(events = merged, liveEvents = canonicalLive, loading = false, refreshing = false, lastUpdatedMs = System.currentTimeMillis(), error = null)
        appContext?.let { StreamPrewarmCoordinator.onSchedulePublished(it, merged) }
    }
    private fun mergeLive(base: List<SportsEvent>, live: List<SportsEvent>): List<SportsEvent> {
        val merged = LinkedHashMap<String, SportsEvent>()
        base.forEach { event -> val key = EventIdentity.key(event); val current = merged[key]; if (current == null || prefer(event, current)) merged[key] = event }
        live.forEach { event -> val key = EventIdentity.key(event); val current = merged[key]; if (current == null || prefer(event, current)) merged[key] = event }
        return merged.values.sortedWith(compareByDescending<SportsEvent> { it.isLive }.thenBy { it.startUtc })
    }
    private fun prefer(candidate: SportsEvent, current: SportsEvent): Boolean {
        val candidateRank = lifecycleRank(candidate.lifecycle); val currentRank = lifecycleRank(current.lifecycle)
        if (candidateRank != currentRank) return candidateRank > currentRank
        val candidateData = listOf(candidate.home, candidate.away, candidate.broadcast, candidate.artUrl).count { it.isNotBlank() }
        val currentData = listOf(current.home, current.away, current.broadcast, current.artUrl).count { it.isNotBlank() }
        return candidateData > currentData
    }
    private fun lifecycleRank(lifecycle: EventLifecycle): Int = when (lifecycle) {
        EventLifecycle.LIVE_CONFIRMED -> 6
        EventLifecycle.LIVE_INFERRED -> 5
        EventLifecycle.PREGAME -> 4
        EventLifecycle.SCHEDULED -> 3
        EventLifecycle.FINAL -> 2
        EventLifecycle.STALE_UNKNOWN -> 1
    }
}
