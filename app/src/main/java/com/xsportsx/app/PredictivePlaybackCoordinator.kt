package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.launch
import java.util.concurrent.ConcurrentHashMap

/**
 * Step 14: predicts the next likely event selection and warms its ranked streams
 * before the user enters playback. Work is bounded and coalesced per event.
 */
object PredictivePlaybackCoordinator {
    private const val MAX_PREDICTIONS = 4
    private const val UPCOMING_WINDOW_MS = 60 * 60 * 1000L
    private const val PREDICTION_TTL_MS = 90 * 1000L

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val inFlight = ConcurrentHashMap<String, Long>()

    fun predict(context: Context, events: List<SportsEvent>, selected: SportsEvent? = null) {
        val now = System.currentTimeMillis()
        val candidates = buildList {
            selected?.let { add(it) }
            addAll(events.filter { it.isLive && selected?.let { e -> EventIdentity.id(e) != EventIdentity.id(it) } != false })
            addAll(events.filter {
                val start = runCatching { java.time.Instant.parse(it.startUtc).toEpochMilli() }.getOrDefault(Long.MAX_VALUE)
                !it.isLive && start in now..(now + UPCOMING_WINDOW_MS)
            }.sortedBy { it.startUtc })
        }.distinctBy { EventIdentity.id(it) }.take(MAX_PREDICTIONS)

        candidates.forEach { event ->
            val key = EventIdentity.id(event)
            val previous = inFlight[key]
            if (previous != null && now - previous < PREDICTION_TTL_MS) return@forEach
            inFlight[key] = now
            scope.launch {
                try {
                    StreamResolver(context.applicationContext).loadMatchingEventStreams(event, force = false)
                } finally {
                    inFlight.remove(key, now)
                }
            }
        }
    }

    fun clear() = inFlight.clear()
}
