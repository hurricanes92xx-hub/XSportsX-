package com.xsportsx.app

import android.content.Context
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player

/**
 * Connects Media3 playback outcomes to the resolver's persistent source health.
 * A source is considered successful only after the player reaches STATE_READY.
 */
class PlaybackSourceFeedback(
    context: Context,
    private val eventId: String,
    private val stream: ResolvedStream,
    private val onFailure: (() -> Unit)? = null,
    private val onSuccess: (() -> Unit)? = null
) : Player.Listener {
    private val resolver = StreamResolver(context)
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
                } else Long.MAX_VALUE
                if (latency != Long.MAX_VALUE) {
                    resolver.recordPlaybackSuccess(eventId, stream, latency)
                    onSuccess?.invoke()
                }
            }
            Player.STATE_IDLE -> {
                if (startedAtMs > 0L && !completed) {
                    completed = true
                    resolver.recordPlaybackFailure(eventId, stream)
                    onFailure?.invoke()
                }
            }
        }
    }

    override fun onPlayerError(error: PlaybackException) {
        if (completed) return
        completed = true
        resolver.recordPlaybackFailure(eventId, stream)
        onFailure?.invoke()
    }
}
