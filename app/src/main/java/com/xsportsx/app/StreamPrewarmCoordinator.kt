package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap

/** Keeps only a tiny working set warm; never competes with the interactive UI. */
object StreamPrewarmCoordinator {
    private const val MAX_LIVE = 2
    private const val MAX_UPCOMING = 2
    private const val UPCOMING_WINDOW_MS = 30 * 60 * 1000L
    private const val PREWARM_TTL_MS = 120 * 1000L

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val lastWarmed = ConcurrentHashMap<String, Long>()
    private val inFlight = ConcurrentHashMap<String, Job>()

    fun onSchedulePublished(context: Context, events: List<SportsEvent>) {
        if (events.isEmpty()) return
        val now = System.currentTimeMillis()
        val targets = events.asSequence()
            .filter { it.isLive || upcomingSoon(it, now) }
            .sortedWith(compareByDescending<SportsEvent> { it.isLive }.thenBy { it.startUtc })
            .take(MAX_LIVE + MAX_UPCOMING)
            .toList()

        targets.forEach { event ->
            val id = EventIdentity.id(event)
            val previous = lastWarmed[id] ?: 0L
            if (now - previous < PREWARM_TTL_MS || inFlight.containsKey(id)) return@forEach
            lastWarmed[id] = now
            inFlight[id] = scope.launch {
                try {
                    StreamResolver(context.applicationContext).loadMatchingEventStreams(event, force = false)
                } finally {
                    inFlight.remove(id)
                }
            }
        }

        if (lastWarmed.size > 128) {
            val cutoff = now - (PREWARM_TTL_MS * 4)
            lastWarmed.entries.removeIf { it.value < cutoff }
        }
    }

    private fun upcomingSoon(event: SportsEvent, now: Long): Boolean {
        if (event.isLive) return false
        val start = runCatching { java.time.Instant.parse(event.startUtc).toEpochMilli() }.getOrDefault(Long.MAX_VALUE)
        return start in now..(now + UPCOMING_WINDOW_MS)
    }
}
