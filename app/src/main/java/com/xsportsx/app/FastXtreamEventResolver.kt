package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Cached-first Xtream resolver. Matching is broadcast-aware: a game does not need
 * to contain the team names in the provider channel name when the channel is a
 * plausible broadcaster for that sport/league.
 *
 * Xtream/authorized results are intentionally resolved before any public-source
 * resolver. Once five good authorized matches exist, discovery stops immediately.
 */
class FastXtreamEventResolver(context: Context) {
    private val store = SourceStore(context.applicationContext)
    private val index = XtreamSourceIndex(context.applicationContext)

    companion object {
        private const val MAX_CATEGORIES = 12
        private const val COLD_RESOLVE_BUDGET_MS = 3200L
        private const val MAX_MATCHES = 12
        private const val EARLY_MATCHES = 5
    }

    suspend fun resolve(event: SportsEvent): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load()
        if (!config.isConfigured() || config.type != "XTREAM") return@withContext emptyList()

        // Authorized Xtream cache is always first. Do not wait on public discovery
        // when the provider already has usable channels.
        val cached = index.getCachedAll(config)
        match(event, cached.map { toStream(config, it) })
            .takeIf { it.isNotEmpty() }
            ?.let { return@withContext it.take(MAX_MATCHES) }

        val discovered = withTimeoutOrNull(COLD_RESOLVE_BUDGET_MS) {
            index.fastResolve(config, event, MAX_CATEGORIES) { channels ->
                match(event, channels.map { toStream(config, it) }).size >= EARLY_MATCHES
            }
        }.orEmpty()

        // Return immediately from the authorized source. Public/legal discovery,
        // if present elsewhere in the app, should only run after this resolver
        // returns no usable authorized result.
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

        val eventText = normalize("${event.title} ${event.home} ${event.away}")
        val home = normalize(event.home)
        val away = normalize(event.away)
        val league = normalize(event.league)
        val sport = normalize(event.sport)
        val broadcastAliases = aliases(event.broadcast, event.league, event.sport)

        return streams.mapNotNull { stream ->
            val name = normalize(stream.name)
            val group = normalize(stream.group)
            val hay = "$name $group"
            var score = 0

            // Event/team matches remain the strongest signal.
            if (eventText.length >= 8 && hay.contains(eventText)) score += 180
            if (home.length >= 4 && hay.contains(home)) score += 90
            if (away.length >= 4 && hay.contains(away)) score += 90

            meaningfulTokens(home).forEach { if (hay.contains(it)) score += 22 }
            meaningfulTokens(away).forEach { if (hay.contains(it)) score += 22 }

            // League/sport context helps distinguish generic network channels.
            if (league.length >= 3 && hay.contains(league)) score += 35
            if (sport.length >= 3 && hay.contains(sport)) score += 12

            // A known broadcaster is a valid game-level match even when the
            // provider channel has no team/event title in its name.
            val networkHits = broadcastAliases.count { it.length >= 3 && hay.contains(it) }
            if (networkHits > 0) score += 55 + ((networkHits - 1).coerceAtMost(3) * 12)

            // Conference-aware college fallback. These are intentionally below
            // an explicit broadcaster match but above an unrelated sports channel.
            if (isCollege(event)) {
                val collegeNetworks = collegeNetworkAliases(event)
                if (collegeNetworks.any { hay.contains(it) }) score += 38
            }

            // Prefer a channel whose group also identifies the broadcaster/network.
            if (broadcastAliases.any { it.length >= 3 && group.contains(it) }) score += 20

            if (score > 0) score to stream else null
        }
            .sortedByDescending { it.first }
            .map { it.second }
            .distinctBy { it.url }
            .take(MAX_MATCHES)
    }

    private fun aliases(broadcast: String, league: String, sport: String): List<String> {
        val out = linkedSetOf<String>()
        fun add(vararg values: String) { values.forEach { if (it.isNotBlank()) out += normalize(it) } }
        add(broadcast)

        val key = normalize("$broadcast $league $sport")
        when {
            key.contains("espn2") || key.contains("espn 2") -> add("ESPN2", "ESPN 2", "ESPN")
            key.contains("espnu") || key.contains("espn u") -> add("ESPNU", "ESPN U", "ESPN")
            key.contains("espn plus") || key.contains("espn+") -> add("ESPN+", "ESPN Plus", "ESPN")
            key.contains("sec network") || key.contains("secn") -> add("SEC Network", "SECN", "SECN+", "SEC")
            key.contains("acc network") || key.contains("accn") -> add("ACC Network", "ACCN", "ACCNX", "ACC")
            key.contains("big ten") || key.contains("btn") -> add("Big Ten Network", "BTN", "Big Ten")
            key.contains("cbs sports") -> add("CBS Sports Network", "CBS Sports", "CBS")
            key.contains("fox sports") || key.contains("fs1") -> add("FOX Sports", "FOX", "FS1", "FS2")
            key.contains("tnt") -> add("TNT")
            key.contains("tbs") -> add("TBS")
            key.contains("trutv") -> add("truTV", "TRU TV")
            key.contains("peacock") -> add("Peacock", "NBC")
            key.contains("paramount") -> add("Paramount+", "Paramount Plus", "Paramount", "CBS")
            key.contains("fanduel") -> add("FanDuel Sports Network", "FanDuel")
        }

        // If the event has no broadcaster metadata, use sport/league broadcast
        // families as a conservative fallback rather than exact event searches.
        when {
            key.contains("ncaa") || key.contains("college") || key.contains("university") ->
                add("ESPN", "ESPN2", "ESPNU", "ESPN+", "ESPN Plus", "ABC", "CBS", "FOX", "FS1", "SEC Network", "SECN", "ACC Network", "ACCN", "Big Ten Network", "BTN", "CBS Sports Network")
            key.contains("nfl") -> add("ESPN", "ABC", "CBS", "FOX", "NBC", "NFL Network")
            key.contains("mlb") || key.contains("baseball") -> add("ESPN", "FOX", "FS1", "TBS", "MLB Network")
            key.contains("nba") || key.contains("basketball") -> add("ESPN", "ABC", "TNT", "TBS", "NBA TV", "CBS Sports Network")
            key.contains("nhl") || key.contains("hockey") -> add("ESPN", "TNT", "TBS", "NHL Network")
            key.contains("soccer") -> add("ESPN+", "ESPN Plus", "FOX", "FS1", "CBS Sports", "TNT Sports", "TUDN", "Peacock")
        }
        return out.toList()
    }

    private fun collegeNetworkAliases(event: SportsEvent): List<String> {
        val key = normalize("${event.league} ${event.sport} ${event.title}")
        return when {
            key.contains("sec") -> listOf("sec network", "secn", "secn plus", "espn")
            key.contains("acc") -> listOf("acc network", "accn", "accnx", "espn")
            key.contains("big ten") -> listOf("big ten network", "btn", "espn")
            else -> listOf("espn", "espn plus", "abc", "cbs", "fox", "fs1")
        }
    }

    private fun isCollege(event: SportsEvent): Boolean {
        val value = normalize("${event.league} ${event.sport} ${event.title}")
        return value.contains("ncaa") || value.contains("college") || value.contains("university")
    }

    private fun meaningfulTokens(value: String): List<String> = value.split(' ')
        .filter { it.length >= 4 && it !in STOP }
        .take(5)

    private fun normalize(value: String) = value.lowercase()
        .replace("+", " plus ")
        .replace("&", " and ")
        .replace("’", "'")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private fun encode(value: String) = java.net.URLEncoder.encode(value, "UTF-8")
    private val STOP = setOf("the", "and", "with", "from", "team", "club", "state", "states", "vs", "versus", "game", "live", "network", "sports")
}
