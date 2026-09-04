package com.xsportsx.app

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.time.Instant
import java.time.temporal.ChronoUnit

/** Single canonical schedule snapshot shared by Mobile and TV. */
object ScheduleSnapshotRepository {
    private const val SNAPSHOT_TTL_MS = 5 * 60_000L
    private const val LIVE_TTL_MS = 10_000L
    private const val UI_DAYS = 3
    private const val SNAPSHOT_DAYS = 7
    private val snapshotMutex = Mutex()
    private val liveMutex = Mutex()
    @Volatile private var snapshotCache: CachedEvents? = null
    @Volatile private var liveCache: CachedEvents? = null
    private data class CachedEvents(val events: List<SportsEvent>, val loadedAtMs: Long)

    suspend fun all(force: Boolean = false): List<SportsEvent> {
        val cached = snapshotCache
        if (!force && cached != null && age(cached) < SNAPSHOT_TTL_MS) return cached.events
        return snapshotMutex.withLock {
            val again = snapshotCache
            if (!force && again != null && age(again) < SNAPSHOT_TTL_MS) return@withLock again.events
            val normalized = normalize(runCatching { CanonicalScheduleProvider.load(null, SNAPSHOT_DAYS) }.getOrDefault(emptyList()))
            if (normalized.isNotEmpty()) { snapshotCache = CachedEvents(normalized, System.currentTimeMillis()); normalized } else again?.events.orEmpty()
        }
    }

    suspend fun upcoming(league: String? = null, force: Boolean = false): List<SportsEvent> {
        val canonical = league?.let(SportsScheduleService::canonicalLeagueFor)
        val now = Instant.now(); val cutoff = now.plus(UI_DAYS.toLong(), ChronoUnit.DAYS)
        return all(force).asSequence().filter { !it.isLive }
            .filter { event ->
                when {
                    canonical == null -> true
                    canonical.equals("WRESTLING", true) -> {
                        // The UI's WRESTLING category is an umbrella for the
                        // separately sourced WWE/AEW/TNA/AAA schedules.
                        event.league.equals("WWE", true) || event.league.equals("AEW", true) ||
                            event.league.equals("TNA", true) || event.league.equals("AAA Wrestling", true) ||
                            event.league.equals("WRESTLING", true)
                    }
                    else -> SportsScheduleService.canonicalLeagueFor(event.league) == canonical
                }
            }
            .filter { event ->
                val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
                val localDate = start.atZone(java.time.ZoneId.systemDefault()).toLocalDate(); val today = now.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val dateOnly = event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
                val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(UI_DAYS.toLong()))
                dateOnlyInWindow || (!start.isBefore(now.minus(10, ChronoUnit.MINUTES)) && start.isBefore(cutoff))
            }.sortedBy { it.startUtc }.toList()
    }

    suspend fun live(force: Boolean = false): List<SportsEvent> {
        val cached = liveCache
        if (!force && cached != null && age(cached) < LIVE_TTL_MS) return cached.events
        return liveMutex.withLock {
            val again = liveCache
            if (!force && again != null && age(again) < LIVE_TTL_MS) return@withLock again.events
            val fresh = runCatching { CanonicalScheduleProvider.load(null, 1) }.getOrDefault(emptyList())
            val normalized = normalize(fresh).filter { it.isLive }
            if (normalized.isNotEmpty() || fresh.isNotEmpty()) { liveCache = CachedEvents(normalized, System.currentTimeMillis()); normalized } else again?.events.orEmpty()
        }
    }

    fun clear() { snapshotCache = null; liveCache = null }
    private fun age(cache: CachedEvents) = System.currentTimeMillis() - cache.loadedAtMs

    private fun normalize(events: List<SportsEvent>): List<SportsEvent> {
        val seen = LinkedHashSet<String>()
        return events.map { it.copy(league = SportsScheduleService.canonicalLeagueFor(it.league)) }
            .filter { seen.add(eventKey(it)) }
            .sortedWith(compareBy<SportsEvent> { !(it.isLive || it.isPregame()) }.thenBy { it.startUtc })
    }

    /** Collapse common MLB feed aliases before constructing the stable matchup key. */
    private fun eventKey(event: SportsEvent): String {
        val league = clean(event.league)
        val teams = listOf(canonicalTeam(event.away, league), canonicalTeam(event.home, league)).sorted()
        val matchup = if (teams.any { it.isNotBlank() }) teams.joinToString("|") else clean(event.title)
        return "$league|$matchup|${event.startUtc.take(16)}"
    }

    private fun clean(value: String) = value.lowercase().replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")

    private fun canonicalTeam(value: String, league: String): String {
        val n = clean(value)
        if (n.isBlank() || !league.contains("mlb")) return n
        return MLB_ALIASES.entries.firstOrNull { n in it.value }?.key ?: n
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
        "san francisco giants" to setOf("san francisco giants", "giants", "sf giants", "sfg"),
        "seattle mariners" to setOf("seattle mariners", "mariners", "sea"),
        "st louis cardinals" to setOf("st louis cardinals", "cardinals", "st louis", "stl"),
        "tampa bay rays" to setOf("tampa bay rays", "rays", "tb rays", "tbr"),
        "texas rangers" to setOf("texas rangers", "rangers", "tex", "texas"),
        "toronto blue jays" to setOf("toronto blue jays", "blue jays", "toronto", "tor"),
        "washington nationals" to setOf("washington nationals", "nationals", "nats", "was")
    )
}
