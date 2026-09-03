package com.xsportsx.app

/** Playback feedback bridge for the resolver's persistent source ranking. */
class StreamHealth(private val cache: PreResolvedStreamCache) {
    fun recordSuccess(event: SportsEvent, stream: ResolvedStream, latencyMs: Long) {
        cache.recordSuccess(EventIdentity.id(event), stream.url, latencyMs)
    }

    fun recordFailure(event: SportsEvent, stream: ResolvedStream) {
        cache.recordFailure(EventIdentity.id(event), stream.url)
    }
}
