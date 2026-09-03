package com.xsportsx.app

import android.content.Context
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player

/** Connects Media3 playback outcomes to the persistent event-source ranking. */
class PlaybackSourceFeedback(
    context: Context,
    private val eventId: String,
    private val stream: ResolvedStream,
    private val onFailure: (() -> Unit)? = null,
    private val onSuccess: (() -> Unit)? = null
) : Player.Listener {
    private val cache = PreResolvedStreamCache(context.applicationContext)
    private var startedAtMs = 0L
    private var completed = false

    fun start(nowMs: Long = System.currentTimeMillis()) {
        startedAtMs = nowMs
        completed = false
    }

    override fun onPlaybackStateChanged(playbackState: Int) {
        when (playbackState) {
            Player.STATE_READY -> {
                if (completed) return
                completed = true
                val latency = if (startedAtMs > 0L) {
                    (System.currentTimeMillis() - startedAtMs).coerceAtLeast(0L)
                } else 0L
                cache.recordSuccess(eventId, stream.url, latency)
                StreamResolver.invalidateCache()
                onSuccess?.invoke()
            }
            Player.STATE_IDLE -> {
                if (startedAtMs > 0L && !completed) {
                    completed = true
                    cache.recordFailure(eventId, stream.url)
                    StreamResolver.invalidateCache()
                    onFailure?.invoke()
                }
            }
        }
    }

    override fun onPlayerError(error: PlaybackException) {
        if (completed) return
        completed = true
        cache.recordFailure(eventId, stream.url)
        StreamResolver.invalidateCache()
        onFailure?.invoke()
    }
}
