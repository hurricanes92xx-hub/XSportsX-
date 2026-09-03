package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap

/**
 * Keeps the resolver warm ahead of user interaction.
 *
 * Only a small live/upcoming working set is resolved. Existing fresh cache entries
 * are left alone, while stale/missing entries are refreshed in the background.
 */
object StreamPrewarmCoordinator {
    private const val MAX_LIVE = 6
    private const val MAX_UPCOMING = 6
    private const val UPCOMING_WINDOW_MS = 45 * 60 * 1000L
    private const val PREWARM_TTL_MS = 90 * 1000L

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
            if (now - previous < PREWARM_TTL_MS) return@forEach
            if (inFlight.containsKey(id)) return@forEach

            lastWarmed[id] = now
            val job = scope.launch {
                try {
                    // Force only the prewarm pass; normal Play requests can use the
                    // persisted fresh cache and never wait on this background work.
                    StreamResolver(context.applicationContext).loadMatchingEventStreams(event, force = true)
                } finally {
                    inFlight.remove(id)
                }
            }
            inFlight[id] = job
        }

        // Prevent the bookkeeping map from growing forever as the schedule rolls.
        if (lastWarmed.size > 256) {
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
