package com.xsportsx.app

import java.security.MessageDigest
import java.util.concurrent.ConcurrentHashMap

/** Deterministic identity shared by every schedule/live path. */
object EventIdentity {
    fun key(event: SportsEvent): String {
        val league = normalize(event.league)
        val away = normalize(event.away)
        val home = normalize(event.home)
        val title = normalize(event.title)
        val matchup = if (away.isNotBlank() || home.isNotBlank()) listOf(away, home).sorted().joinToString("|") else title
        val minute = event.startUtc.trim().take(16)
        return "$league|$matchup|$minute"
    }

    fun id(event: SportsEvent): String = event.id.trim().ifBlank {
        "evt_${sha256(key(event)).take(24)}"
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace("&", " and ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it) }
}

/** O(1)-style lookup facade for the canonical event collection. */
class EventIndex {
    private val byId = ConcurrentHashMap<String, SportsEvent>()
    private val byKey = ConcurrentHashMap<String, SportsEvent>()

    fun rebuild(events: List<SportsEvent>) {
        byId.clear(); byKey.clear()
        events.forEach { event ->
            val canonical = event.copy(id = EventIdentity.id(event))
            byId[canonical.id] = canonical
            byKey[EventIdentity.key(canonical)] = canonical
        }
    }

    fun get(id: String): SportsEvent? = byId[id]
    fun find(event: SportsEvent): SportsEvent? = byKey[EventIdentity.key(event)] ?: get(event.id)
    fun all(): List<SportsEvent> = byId.values.toList()
}

/**
 * Lightweight channel/network index. It is deliberately independent of schedule state:
 * stream failures can never remove a game from the schedule.
 */
class ChannelIndex {
    private val byToken = ConcurrentHashMap<String, MutableSet<ResolvedStream>>()

    fun rebuild(streams: List<ResolvedStream>) {
        byToken.clear()
        streams.forEach { stream ->
            tokens(stream).forEach { token ->
                byToken.computeIfAbsent(token) { LinkedHashSet() }.add(stream)
            }
        }
    }

    fun find(query: String, limit: Int = 16): List<ResolvedStream> {
        val terms = normalize(query).split(' ').filter { it.length >= 3 }.distinct()
        if (terms.isEmpty()) return emptyList()
        val candidates = LinkedHashSet<ResolvedStream>()
        terms.forEach { token -> byToken[token].orEmpty().forEach(candidates::add) }
        return candidates
            .sortedByDescending { score(it, terms) }
            .take(limit)
    }

    fun size(): Int = byToken.values.sumOf { it.size }

    private fun score(stream: ResolvedStream, terms: List<String>): Int {
        val haystack = normalize("${stream.name} ${stream.group}")
        return terms.count { haystack.contains(it) }
    }

    private fun tokens(stream: ResolvedStream): List<String> = normalize("${stream.name} ${stream.group}")
        .split(' ')
        .filter { it.length >= 3 }
        .distinct()

    private fun normalize(value: String): String = value.lowercase()
        .replace("+", " plus ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")
}
