package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Fast click-path selector. Cached health results are only a fast head start;
 * they never prevent a fresh targeted search across public and user-connected
 * sources. This prevents the health index from masking newly discovered public feeds.
 */
class FastPublicSourceSelector(context: Context) {
    private val index = PublicSourceHealthIndex(context)
    private val resolver = TargetedSourceResolver()

    suspend fun candidates(
        event: SportsEvent,
        authorizedSources: List<AuthorizedSource> = emptyList(),
        limit: Int = 8
    ): List<TargetedStream> = withContext(Dispatchers.IO) {
        val known = index.rank(event.id, event.sport, event.league, event.broadcast, limit)
        val knownUrls = known.map { normalizeUrl(it.url) }.toSet()
        val knownResults = known.map { h ->
            TargetedStream(
                name = h.channel,
                group = h.league,
                url = h.url,
                sourceId = "health-index",
                sourceType = "KNOWN",
                score = 100
            )
        }

        // Always perform a fresh targeted search. A stale/overconfident health
        // index must never short-circuit public, M3U, or Xtream discovery.
        val discovered = runCatching {
            resolver.search(TargetQuery(event = event), authorizedSources)
        }.getOrDefault(emptyList())

        (knownResults + discovered.filterNot { normalizeUrl(it.url) in knownUrls })
            .distinctBy { normalizeUrl(it.url) }
            .sortedWith(compareByDescending<TargetedStream> { it.score }.thenBy { it.sourceType })
            .take(limit)
    }

    suspend fun candidatesForNetwork(
        network: String,
        event: SportsEvent? = null,
        authorizedSources: List<AuthorizedSource> = emptyList(),
        limit: Int = 8
    ): List<TargetedStream> = withContext(Dispatchers.IO) {
        runCatching {
            resolver.search(TargetQuery(event = event, network = network), authorizedSources)
        }.getOrDefault(emptyList())
            .take(limit)
    }

    fun record(stream: TargetedStream, event: SportsEvent, success: Boolean) {
        index.record(
            PublicResolvedStream(
                name = stream.name,
                group = stream.group,
                url = stream.url,
                sourceName = stream.sourceId,
                latencyMs = 0
            ),
            event.sport,
            event.league,
            event.id,
            event.broadcast,
            success
        )
    }

    private fun normalizeUrl(value: String): String = value.trim().trimEnd('/').lowercase()
}
