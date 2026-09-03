package com.xsportsx.app

import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap

/** Deterministic identity shared by every schedule/live path. */
object EventIdentity {
    fun key(event: SportsEvent): String {
        val league = normalize(event.league)
        val away = canonicalTeam(event.away, league)
        val home = canonicalTeam(event.home, league)
        val title = normalize(event.title)
        val matchup = if (away.isNotBlank() || home.isNotBlank()) listOf(away, home).sorted().joinToString("|") else title
        val bucket = startBucket(event.startUtc)
        return "$league|$matchup|$bucket"
    }

    fun id(event: SportsEvent): String = event.id.trim().ifBlank { "evt_${sha256(key(event)).take(24)}" }

    private fun startBucket(startUtc: String): Long {
        val millis = runCatching { Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)
        return if (millis > 0L) millis / (2L * 60L * 60L * 1000L) else 0L
    }

    private fun normalize(value: String): String = value.lowercase()
        .replace("&", " and ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")

    private fun canonicalTeam(value: String, league: String): String {
        val n = normalize(value)
        if (n.isBlank()) return n
        if (league.contains("mlb") || league.contains("baseball")) {
            MLB_ALIASES.entries.firstOrNull { n in it.value }?.key?.let { return it }
        }
        return n
    }

    private val MLB_ALIASES = mapOf(
        "arizona diamondbacks" to setOf("arizona diamondbacks", "diamondbacks", "dbacks", "d backs", "ari"),
        "atlanta braves" to setOf("atlanta braves", "braves", "atl"),
        "baltimore orioles" to setOf("baltimore orioles", "orioles", "bal"),
        "boston red sox" to setOf("boston red sox", "red sox", "bos"),
        "chicago cubs" to setOf("chicago cubs", "cubs", "chi cubs", "chc"),
        "chicago white sox" to setOf("chicago white sox", "white sox", "chi white sox", "chisox", "cws"),
        "cincinnati reds" to setOf("cincinnati reds", "reds", "cin"),
        "cleveland guardians" to setOf("cleveland guardians", "guardians", "cleveland indians", "cle"),
        "colorado rockies" to setOf("colorado rockies", "rockies", "col"),
        "detroit tigers" to setOf("detroit tigers", "tigers", "det"),
        "houston astros" to setOf("houston astros", "astros", "hou", "houston"),
        "kansas city royals" to setOf("kansas city royals", "royals", "kc royals", "kcr"),
        "los angeles angels" to setOf("los angeles angels", "la angels", "angels", "ana"),
        "los angeles dodgers" to setOf("los angeles dodgers", "la dodgers", "dodgers", "lad"),
        "miami marlins" to setOf("miami marlins", "marlins", "mia"),
        "milwaukee brewers" to setOf("milwaukee brewers", "brewers", "mil"),
        "minnesota twins" to setOf("minnesota twins", "twins", "min"),
        "new york mets" to setOf("new york mets", "mets", "nym"),
        "new york yankees" to setOf("new york yankees", "yankees", "nyy"),
        "oakland athletics" to setOf("oakland athletics", "athletics", "oak"),
        "philadelphia phillies" to setOf("philadelphia phillies", "phillies", "phi"),
        "pittsburgh pirates" to setOf("pittsburgh pirates", "pirates", "pit", "pittsburgh"),
        "san diego padres" to setOf("san diego padres", "padres", "sdp"),
        "san francisco giants" to setOf("san francisco giants", "giants", "sf giants", "sfg", "san francisco"),
        "seattle mariners" to setOf("seattle mariners", "mariners", "sea"),
        "st louis cardinals" to setOf("st louis cardinals", "cardinals", "st louis", "stl"),
        "tampa bay rays" to setOf("tampa bay rays", "rays", "tb rays", "tbr"),
        "texas rangers" to setOf("texas rangers", "rangers", "tex", "texas"),
        "toronto blue jays" to setOf("toronto blue jays", "blue jays", "toronto", "tor"),
        "washington nationals" to setOf("washington nationals", "nationals", "nats", "was")
    )

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
}

/** O(1)-style lookup facade for the canonical event collection. */
class EventIndex {
    private val byId = ConcurrentHashMap<String, SportsEvent>()
    private val byKey = ConcurrentHashMap<String, SportsEvent>()
    fun rebuild(events: List<SportsEvent>) {
        byId.clear(); byKey.clear()
        events.forEach { event -> val canonical = event.copy(id = EventIdentity.id(event)); byId[canonical.id] = canonical; byKey[EventIdentity.key(canonical)] = canonical }
    }
    fun get(id: String): SportsEvent? = byId[id]
    fun find(event: SportsEvent): SportsEvent? = byKey[EventIdentity.key(event)] ?: get(event.id)
    fun all(): List<SportsEvent> = byId.values.toList()
}

class ChannelIndex {
    private val byToken = ConcurrentHashMap<String, MutableSet<ResolvedStream>>()
    fun rebuild(streams: List<ResolvedStream>) {
        byToken.clear(); streams.forEach { stream -> tokens(stream).forEach { token -> byToken.computeIfAbsent(token) { LinkedHashSet() }.add(stream) } }
    }
    fun find(query: String, limit: Int = 16): List<ResolvedStream> {
        val terms = normalize(query).split(' ').filter { it.length >= 3 }.distinct(); if (terms.isEmpty()) return emptyList()
        val candidates = LinkedHashSet<ResolvedStream>(); terms.forEach { token -> byToken[token].orEmpty().forEach(candidates::add) }
        return candidates.sortedByDescending { score(it, terms) }.take(limit)
    }
    fun size(): Int = byToken.values.sumOf { it.size }
    private fun score(stream: ResolvedStream, terms: List<String>): Int { val haystack = normalize("${stream.name} ${stream.group}"); return terms.count { haystack.contains(it) } }
    private fun tokens(stream: ResolvedStream): List<String> = normalize("${stream.name} ${stream.group}").split(' ').filter { it.length >= 3 }.distinct()
    private fun normalize(value: String): String = value.lowercase().replace("+", " plus ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
}
