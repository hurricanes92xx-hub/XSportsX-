package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext

/**
 * Event-first matcher for public sports sources. Event discovery is targeted so
 * a game click never waits for the full public catalog + global health sweep.
 */
class PublicEventMatcher(private val resolver: PublicSourceResolver = PublicSourceResolver()) {
    suspend fun find(event: SportsEvent, force: Boolean = false, maxResults: Int = 8): List<PublicResolvedStream> =
        withContext(Dispatchers.Default) {
            val terms = listOf(
                event.home,
                event.away,
                event.title,
                event.broadcast,
                event.league,
                event.sport
            ).filter { it.isNotBlank() }

            // Search only the relevant playlists for this event. The old path
            // loaded the entire public catalog and then health-checked up to 240
            // streams, which could leave a game click spinning for a long time.
            val streams = resolver.searchTargeted(terms)
            val ranked = streams.mapNotNull { stream ->
                val score = score(event, stream)
                if (score <= 0) null else score to stream
            }.sortedByDescending { it.first }

            coroutineScope {
                ranked.take(maxResults * 4).map { (score, stream) ->
                    async(Dispatchers.IO) { score to stream }
                }.awaitAll()
            }.sortedByDescending { it.first }.take(maxResults).map { it.second }
        }

    private fun score(event: SportsEvent, stream: PublicResolvedStream): Int {
        val haystack = normalize("${stream.name} ${stream.group} ${stream.sourceName}")
        val home = normalize(event.home)
        val away = normalize(event.away)
        val title = normalize(event.title)
        val league = normalize(event.league)
        val broadcast = normalize(event.broadcast)
        val sport = normalize(event.sport)
        var score = 0

        if (title.length >= 4 && haystack.contains(title)) score += 100
        if (home.length >= 3 && haystack.contains(home)) score += 75
        if (away.length >= 3 && haystack.contains(away)) score += 75

        val homeTokens = meaningfulTokens(home)
        val awayTokens = meaningfulTokens(away)
        if (homeTokens.isNotEmpty() && homeTokens.any { haystack.contains(it) }) score += 25
        if (awayTokens.isNotEmpty() && awayTokens.any { haystack.contains(it) }) score += 25

        if (league.length >= 2 && haystack.contains(league)) score += 30
        if (broadcast.length >= 3 && haystack.contains(broadcast)) score += 45
        if (sport.length >= 3 && haystack.contains(sport)) score += 10

        val broadcastAliases = broadcastAliasesFor(event)
        for (alias in broadcastAliases) {
            val n = normalize(alias)
            if (n.length >= 3 && haystack.contains(n)) {
                score += if (n == broadcast) 50 else 22
                break
            }
        }

        if (isCollege(event)) {
            val collegeTerms = listOf(
                "ncaa", "college", "university", "volleyball", "basketball",
                "acccdn", "accdn", "acc network", "accnx", "secn", "sec network",
                "btn", "big ten network", "pac 12 insider", "espn+", "espn plus",
                "school", "athletics", "conference"
            )
            if (collegeTerms.any { haystack.contains(normalize(it)) }) score += 14
        }

        return score
    }

    private fun broadcastAliasesFor(event: SportsEvent): List<String> {
        val base = listOf(event.broadcast, event.league, event.sport)
        val key = normalize("${event.league} ${event.sport} ${event.broadcast}")
        val aliases = mutableListOf<String>()
        aliases += base

        fun add(vararg values: String) { aliases += values }

        when {
            key.contains("volleyball") -> add(
                "ESPN", "ESPN2", "ESPNU", "ESPN+", "ESPN Plus", "SEC Network", "SECN+",
                "ACC Network", "ACCNX", "ACCDN", "Big Ten Network", "BTN", "CBS Sports Network",
                "The CW", "CW Sports", "Pac-12 Insider", "NCAA", "Volleyball World"
            )
            key.contains("basketball") -> add(
                "ESPN", "ESPN2", "ESPNU", "ESPN+", "ESPN Plus", "ABC", "CBS", "CBS Sports Network",
                "FOX", "FS1", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX",
                "ACCDN", "Big Ten Network", "BTN", "The CW", "CW Sports", "Pac-12 Insider"
            )
            key.contains("football") -> add(
                "ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "FOX", "FS1", "FS2", "CBS",
                "CBS Sports Network", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network",
                "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "Pac-12 Insider"
            )
            key.contains("baseball") -> add(
                "ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX",
                "Big Ten Network", "BTN", "CBS Sports Network", "FOX", "FS1", "MLB Network", "NCAA"
            )
            key.contains("softball") -> add(
                "ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX",
                "Big Ten Network", "BTN", "CBS Sports Network", "NCAA"
            )
            key.contains("soccer") -> add(
                "ESPN+", "ESPN Plus", "ACC Network", "ACCNX", "SEC Network", "SECN+", "Big Ten Network",
                "BTN", "CBS Sports Golazo", "The CW", "Peacock", "FOX Sports", "TUDN", "Telemundo", "Universo"
            )
            key.contains("lacrosse") -> add(
                "ESPN+", "ESPN Plus", "ESPNU", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "NCAA"
            )
            key.contains("wrestling") -> add(
                "ESPN+", "ESPN Plus", "Big Ten Network", "BTN", "ESPNU", "ACC Network", "ACCNX", "NCAA"
            )
            key.contains("gymnastics") -> add(
                "ESPN+", "ESPN Plus", "SEC Network", "SECN+", "Big Ten Network", "BTN", "ACC Network", "ACCNX"
            )
            key.contains("hockey") -> add(
                "ESPN+", "ESPN Plus", "Big Ten Network", "BTN", "ESPNU", "NHL Network", "NCAA"
            )
            key.contains("track") || key.contains("cross country") -> add(
                "ESPN+", "ESPN Plus", "SEC Network+", "SECN+", "ACC Network", "ACCNX", "NCAA"
            )
            else -> add("ESPN", "ESPN+", "ESPN Plus", "CBS Sports Network", "The CW", "CW Sports", "NCAA")
        }

        return aliases.distinct()
    }

    private fun isCollege(event: SportsEvent): Boolean {
        val value = normalize("${event.league} ${event.sport} ${event.title}")
        return value.contains("ncaa") || value.contains("college") ||
            value.contains("university") || value.contains("mens college") || value.contains("womens college")
    }

    private fun meaningfulTokens(value: String): List<String> =
        value.split(' ').filter { it.length >= 4 && it !in STOP_WORDS }.take(4)

    private fun normalize(value: String): String = value.lowercase()
        .replace("&", " and ")
        .replace("’", "'")
        .replace("+", " plus ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private companion object {
        val STOP_WORDS = setOf("the", "and", "team", "club", "united", "state", "states")
    }
}