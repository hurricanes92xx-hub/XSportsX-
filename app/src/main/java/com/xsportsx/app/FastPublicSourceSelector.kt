package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Fast click-path selector. It searches only the selected event/network across
 * public and user-connected sources instead of preloading a global catalog.
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
        val knownUrls = known.map { it.url }.toSet()
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

        if (knownResults.size >= limit) return@withContext knownResults.take(limit)

        val discovered = runCatching {
            resolver.search(TargetQuery(event = event), authorizedSources)
        }.getOrDefault(emptyList())

        (knownResults + discovered.filterNot { it.url in knownUrls })
            .distinctBy { it.url }
            .sortedWith(compareByDescending<TargetedStream> { it.score })
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
}
