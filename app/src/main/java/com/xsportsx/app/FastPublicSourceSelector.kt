package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Selects already-known public candidates first; discovery stays off the click path. */
class FastPublicSourceSelector(context: Context) {
    private val index = PublicSourceHealthIndex(context)
    private val resolver = PublicSourceResolver()

    suspend fun candidates(event: SportsEvent, limit: Int = 8): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val known = index.rank(event.id, event.sport, event.league, event.broadcast, limit)
        val knownUrls = known.map { it.url }.toSet()
        val ranked = known.map { h -> PublicResolvedStream(h.channel, h.league, h.url, sourceName = "Public source (known healthy)", latencyMs = h.latencyMs) }.toMutableList()
        if (ranked.size >= limit) return@withContext ranked.take(limit)

        // Cold-start only: populate from the cached/public registry, never from the UI thread.
        val discovered = runCatching { resolver.load() }.getOrDefault(emptyList())
        ranked += discovered.filterNot { it.url in knownUrls }
            .filter { matchesEvent(it, event) }
            .sortedBy { it.latencyMs }
            .take(limit - ranked.size)
        ranked.distinctBy { it.url }.take(limit)
    }

    fun record(stream: PublicResolvedStream, event: SportsEvent, success: Boolean) {
        index.record(stream, event.sport, event.league, event.id, event.broadcast, success)
    }

    private fun matchesEvent(stream: PublicResolvedStream, event: SportsEvent): Boolean {
        val hay = "${stream.name} ${stream.group} ${stream.sourceName}"
        val terms = listOf(event.league, event.broadcast, event.home, event.away).filter { it.isNotBlank() }
        return terms.any { term -> hay.contains(term, true) } || hay.contains(event.sport, true)
    }
}
