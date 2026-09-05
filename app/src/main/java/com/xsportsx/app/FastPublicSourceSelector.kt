package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Fast click-path selector. Known healthy and pre-resolved event streams are returned
 * immediately. Fresh discovery is only used when the local indexes have no usable answer.
 */
class FastPublicSourceSelector(context: Context) {
    private val index = PublicSourceHealthIndex(context)
    private val preResolved = PreResolvedStreamCache(context)
    private val resolver = TargetedSourceResolver()

    companion object {
        private const val DISCOVERY_BUDGET_MS = 7_000L
    }

    suspend fun candidates(
        event: SportsEvent,
        authorizedSources: List<AuthorizedSource> = emptyList(),
        limit: Int = 8
    ): List<TargetedStream> = withContext(Dispatchers.IO) {
        val eventId = EventIdentity.id(event)

        // First priority: candidates discovered by the background prewarmer. This is
        // the zero-network path and survives screen navigation/app recreation.
        preResolved.get(eventId, allowStale = true)?.let { cached ->
            val results = cached.candidates.map { candidate ->
                TargetedStream(
                    name = candidate.stream.name,
                    group = candidate.stream.group,
                    url = candidate.stream.url,
                    sourceId = "pre-resolved",
                    sourceType = "CACHED",
                    score = 110 - candidate.rank
                )
            }
            if (results.isNotEmpty()) return@withContext results.take(limit)
        }

        val known = index.rank(eventId, event.sport, event.league, event.broadcast, limit)
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
        if (knownResults.isNotEmpty()) return@withContext knownResults.take(limit)

        // Cold path: one bounded discovery. The UI gets a real chance to finish the
        // authorized Xtream/category lookup instead of abandoning it after 3.5 seconds.
        val discovered = withTimeoutOrNull(DISCOVERY_BUDGET_MS) {
            runCatching { resolver.search(TargetQuery(event = event), authorizedSources) }
                .getOrDefault(emptyList())
        }.orEmpty()

        discovered
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
        withTimeoutOrNull(DISCOVERY_BUDGET_MS) {
            runCatching {
                resolver.search(TargetQuery(event = event, network = network), authorizedSources)
            }.getOrDefault(emptyList())
        }.orEmpty().take(limit)
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
