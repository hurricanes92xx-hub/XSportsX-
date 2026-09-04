package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Fast click-path selector. Known healthy event streams are returned immediately.
 * A fresh discovery is only used when the index has no usable answer and is bounded
 * so a slow public playlist can never block the player screen indefinitely.
 */
class FastPublicSourceSelector(context: Context) {
    private val index = PublicSourceHealthIndex(context)
    private val resolver = TargetedSourceResolver()

    companion object {
        private const val DISCOVERY_BUDGET_MS = 3_500L
    }

    suspend fun candidates(
        event: SportsEvent,
        authorizedSources: List<AuthorizedSource> = emptyList(),
        limit: Int = 8
    ): List<TargetedStream> = withContext(Dispatchers.IO) {
        val known = index.rank(event.id, event.sport, event.league, event.broadcast, limit)
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

        // Known-good answers are the zero-wait path. The old implementation always
        // performed a network search even when it already had a usable source, which
        // is exactly the kind of delay that produced "Stream search timed out".
        if (knownResults.isNotEmpty()) return@withContext knownResults.take(limit)

        // No cached answer: perform one targeted discovery, but enforce a hard budget.
        // This keeps a dead/slow public playlist from holding the UI hostage.
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
