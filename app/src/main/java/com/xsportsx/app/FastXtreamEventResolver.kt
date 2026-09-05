package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/** Cached-first, bounded Xtream event resolver backed by the shared metadata index. */
class FastXtreamEventResolver(context: Context) {
    private val store = SourceStore(context.applicationContext)
    private val index = XtreamSourceIndex(context.applicationContext)

    companion object {
        private const val MAX_CATEGORIES = 8
        private const val COLD_RESOLVE_BUDGET_MS = 3200L
        private const val MAX_MATCHES = 12
    }

    suspend fun resolve(event: SportsEvent): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load()
        if (!config.isConfigured() || config.type != "XTREAM") return@withContext emptyList()

        // Hot path: persisted/in-memory channels only. This must never touch the network.
        val cached = index.getCachedAll(config)
        match(event, cached.map { toStream(config, it) })
            .takeIf { it.isNotEmpty() }
            ?.let { return@withContext it }

        // Cold path: the shared index uses cached categories and parallel category calls.
        // It is deliberately bounded so the UI never waits on a full Xtream catalogue.
        val discovered = withTimeoutOrNull(COLD_RESOLVE_BUDGET_MS) {
            index.fastResolve(config, event, MAX_CATEGORIES)
        }.orEmpty()
        match(event, discovered.map { toStream(config, it) }).take(MAX_MATCHES)
    }

    private fun toStream(config: SourceConfig, channel: XtreamSourceIndex.Channel) = ResolvedStream(
        channel.name,
        channel.group,
        "${config.server.trim().removeSuffix("/")}/live/${encode(config.username)}/${encode(config.password)}/${channel.id}.m3u8",
        channel.icon
    )

    private fun match(event: SportsEvent, streams: List<ResolvedStream>): List<ResolvedStream> {
        if (streams.isEmpty()) return emptyList()
        val teams = terms("${event.home} ${event.away}")
        val league = terms(event.league)
        val broadcast = aliases(event.broadcast)
        return streams.mapNotNull { stream ->
            val hay = normalize("${stream.name} ${stream.group}")
            val teamHits = teams.count { it.length >= 4 && hay.contains(it) }
            val leagueHits = league.count { it.length >= 3 && hay.contains(it) }
            val networkHits = broadcast.count { it.length >= 3 && hay.contains(it) }
            val strong = teams.size >= 2 && teamHits >= 2
            val oneTeamWithContext = teamHits >= 1 && (leagueHits > 0 || networkHits > 0)
            val networkOnly = networkHits > 0 && (event.broadcast.isNotBlank() || event.league.contains("NCAA", true))
            if (strong || oneTeamWithContext || networkOnly) {
                (teamHits * 50 + leagueHits * 8 + networkHits * 15) to stream
            } else null
        }.sortedByDescending { it.first }.map { it.second }.distinctBy { it.url }.take(MAX_MATCHES)
    }

    private fun terms(value: String) = normalize(value).split(' ')
        .filter { it.length >= 3 && it !in STOP }.distinct()

    private fun aliases(value: String): List<String> {
        val n = normalize(value)
        if (n.isBlank()) return emptyList()
        val out = linkedSetOf(n)
        if (n.contains("espn plus")) out += listOf("espn", "espn plus", "espn+")
        if (n.contains("espn2")) out += listOf("espn2", "espn 2", "espn")
        if (n.contains("espnu")) out += listOf("espnu", "espn u", "espn")
        if (n.contains("sec network")) out += listOf("sec network", "secn", "sec")
        if (n.contains("acc network")) out += listOf("acc network", "accn", "acc")
        if (n.contains("big ten")) out += listOf("big ten network", "btn", "big ten")
        return out.map(::normalize).distinct()
    }

    private fun normalize(value: String) = value.lowercase()
        .replace("+", " plus ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private fun encode(value: String) = java.net.URLEncoder.encode(value, "UTF-8")
    private val STOP = setOf("the", "and", "with", "vs", "versus", "game", "live", "network", "sports")
}
