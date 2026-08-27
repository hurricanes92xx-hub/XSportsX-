package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Event-first search adapter.
 * SportsEvent is owned by SportsScheduleService so schedules, favorites,
 * and the finder all use one model instead of competing declarations.
 */
data class EventSearchResult(val event: SportsEvent, val score: Int)
data class EventStreamSearchResult(val event: SportsEvent, val streams: List<ResolvedStream>)

class EventFinder {
    private val streamResolver by lazy { EventStreamResolverHolder.resolver }

    suspend fun search(query: String, maxResults: Int = 20): List<EventSearchResult> = withContext(Dispatchers.IO) {
        val q = normalize(query)
        if (q.length < 2) return@withContext emptyList()
        val events = runCatching { SportsScheduleService.load() }.getOrDefault(emptyList())

        events.asSequence()
            .map { EventSearchResult(it, score(q, it)) }
            .filter { it.score > 0 }
            .sortedWith(compareByDescending<EventSearchResult> { it.score }.thenBy { it.event.startUtc })
            .distinctBy { it.event.id.ifBlank { it.event.title + it.event.startUtc } }
            .take(maxResults)
            .toList()
    }

    /** Strong matching for UFC Fight Night, Fight Night, UFC, or fighter/event names. */
    suspend fun searchUfcFightNight(
        query: String = "UFC Fight Night",
        maxResults: Int = 20
    ): List<EventSearchResult> = withContext(Dispatchers.IO) {
        val q = normalize(query)
        if (q.length < 2) return@withContext emptyList()

        val events = runCatching { SportsScheduleService.load() }.getOrDefault(emptyList())
            .filter { it.league.equals("UFC", true) || it.sport.equals("MMA", true) }

        events.asSequence()
            .map { event ->
                var s = score(q, event)
                val title = normalize(event.title)
                if (q.contains("fight night") && title.contains("fight night")) s = maxOf(s, 100)
                if (q == "ufc" && event.league.equals("UFC", true)) s = maxOf(s, 95)
                EventSearchResult(event, s)
            }
            .filter { it.score > 0 }
            .sortedWith(compareByDescending<EventSearchResult> { it.score }.thenBy { it.event.startUtc })
            .distinctBy { it.event.id.ifBlank { it.event.title + it.event.startUtc } }
            .take(maxResults)
            .toList()
    }

    /**
     * Full event-first flow: find the real scheduled event, then ask the
     * stream resolver for matching authorized/public streams. This keeps a
     * search such as "UFC Fight Night" from devolving into generic sports
     * channels when a matching event is available.
     */
    suspend fun searchWithStreams(query: String, maxResults: Int = 8): List<EventStreamSearchResult> = withContext(Dispatchers.IO) {
        val matches = if (normalize(query).contains("ufc") || normalize(query).contains("fight night")) {
            searchUfcFightNight(query, maxResults)
        } else search(query, maxResults)

        matches.mapNotNull { match ->
            val streams = runCatching { streamResolver.loadMatchingEventStreams(match.event) }
                .getOrDefault(emptyList())
            if (streams.isEmpty()) null else EventStreamSearchResult(match.event, streams)
        }
    }

    private fun score(q: String, event: SportsEvent): Int {
        val fields = listOf(event.title, event.home, event.away, event.league, event.sport, event.broadcast).map(::normalize)
        if (fields.any { it == q }) return 100
        if (fields.any { it.contains(q) }) return 92

        val tokens = q.split(' ').filter { it.length >= 2 }
        if (tokens.isEmpty()) return 0
        val hits = tokens.count { token -> fields.any { it.contains(token) } }
        return when {
            hits == tokens.size -> 86
            hits >= 2 -> 65
            hits == 1 && tokens.size == 1 -> 48
            else -> 0
        }
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace("’", "'")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")
}

/** Keeps the finder usable without making the UI own resolver construction. */
private object EventStreamResolverHolder {
    lateinit var resolver: StreamResolver
}
