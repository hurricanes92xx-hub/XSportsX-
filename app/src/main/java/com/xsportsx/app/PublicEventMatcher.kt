package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext

/**
 * Matches schedule events to the public-source catalog without requiring an
 * Xtream or M3U login. Matching is deliberately event-first: teams/fighters,
 * league, sport and broadcast/network are scored before a stream is offered.
 */
class PublicEventMatcher(private val resolver: PublicSourceResolver = PublicSourceResolver()) {
    suspend fun find(event: SportsEvent, force: Boolean = false, maxResults: Int = 8): List<PublicResolvedStream> =
        withContext(Dispatchers.Default) {
            val streams = resolver.load(force)
            val ranked = streams.mapNotNull { stream ->
                val score = score(event, stream)
                if (score <= 0) null else score to stream
            }.sortedByDescending { it.first }

            coroutineScope {
                ranked.take(maxResults * 3).map { (score, stream) ->
                    async(Dispatchers.IO) {
                        // The public resolver already health-checks its catalog;
                        // event matching only ranks those verified candidates.
                        score to stream
                    }
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

        // Exact event/team/fighter references are strongest.
        if (title.length >= 4 && haystack.contains(title)) score += 100
        if (home.length >= 3 && haystack.contains(home)) score += 75
        if (away.length >= 3 && haystack.contains(away)) score += 75

        // Common abbreviated team names are useful for M3U labels.
        val homeTokens = meaningfulTokens(home)
        val awayTokens = meaningfulTokens(away)
        if (homeTokens.isNotEmpty() && homeTokens.any { haystack.contains(it) }) score += 25
        if (awayTokens.isNotEmpty() && awayTokens.any { haystack.contains(it) }) score += 25

        if (league.length >= 2 && haystack.contains(league)) score += 30
        if (broadcast.length >= 3 && haystack.contains(broadcast)) score += 45
        if (sport.length >= 3 && haystack.contains(sport)) score += 10

        // Network fallback: if no event/team label exists, a matching official
        // network remains useful for the event's broadcast.
        val networkTerms = listOf("espn", "espn2", "espnu", "espn+", "fox sports", "fs1", "fs2", "tnt", "tbs", "tru tv", "nbc", "cbs", "abc", "nfl network", "nba tv", "mlb network", "nhl network", "sec network", "acc network", "big ten network", "the cw")
        if (networkTerms.any { haystack.contains(it) && (broadcast.contains(it) || broadcast.isBlank()) }) score += 18

        return score
    }

    private fun meaningfulTokens(value: String): List<String> =
        value.split(' ').filter { it.length >= 4 && it !in STOP_WORDS }.take(4)

    private fun normalize(value: String): String = value.lowercase()
        .replace("&", " and ")
        .replace("’", "'")
        .replace(Regex("[^a-z0-9+]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private companion object {
        val STOP_WORDS = setOf("the", "and", "team", "club", "united", "state", "states")
    }
}
