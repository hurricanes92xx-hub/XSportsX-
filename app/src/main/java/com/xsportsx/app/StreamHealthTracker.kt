package com.xsportsx.app

/**
 * Lightweight playback feedback bridge. It records only resolver health metadata;
 * it never probes or contacts a stream on its own.
 */
class StreamHealthTracker(private val cache: PreResolvedStreamCache) {
    fun success(eventId: String, stream: ResolvedStream, latencyMs: Long = Long.MAX_VALUE) {
        cache.recordSuccess(eventId, stream, latencyMs)
    }

    fun failure(eventId: String, stream: ResolvedStream) {
        cache.recordFailure(eventId, stream)
    }
}
