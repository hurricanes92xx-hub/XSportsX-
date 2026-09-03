package com.xsportsx.app

import android.content.Context

/**
 * Single decision layer for stream candidate ordering.
 * Combines URL health, event-specific playback history, global playback history,
 * and measured latency without probing streams just to rank them.
 */
class SourceHealthDecisionEngine(context: Context) {
    private val streamHealth = StreamHealthStore(context.applicationContext)
    private val playbackHealth = PlaybackHealthStore(context.applicationContext)

    fun rank(eventId: String, streams: List<ResolvedStream>): List<ResolvedStream> {
        if (streams.size < 2) return streams
        val now = System.currentTimeMillis()
        return streams.withIndex()
            .sortedWith(
                compareByDescending<IndexedValue<ResolvedStream>> {
                    decisionScore(eventId, it.value, now)
                }.thenBy { it.index }
            )
            .map { it.value }
    }

    private fun decisionScore(eventId: String, stream: ResolvedStream, now: Long): Double {
        val urlHealth = streamHealth.score(stream.url, now).toDouble()
        val eventPlayback = if (eventId.isBlank()) 0.0 else playbackHealth.score(eventId, stream)
        val globalPlayback = playbackHealth.globalScore(stream)
        val health = streamHealth.health(stream.url)
        val latencyBonus = if (health.lastLatencyMs != Long.MAX_VALUE) {
            (500.0 / health.lastLatencyMs.coerceAtLeast(100L)).coerceAtMost(5.0)
        } else 0.0
        return urlHealth + (eventPlayback * 1.5) + globalPlayback + latencyBonus
    }
}
