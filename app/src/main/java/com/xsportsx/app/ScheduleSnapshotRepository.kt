package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** Single canonical schedule snapshot shared by Mobile and TV. */
object ScheduleSnapshotRepository {
    private const val SNAPSHOT_TTL_MS = 5 * 60_000L
    private const val LIVE_TTL_MS = 10_000L
    private const val UI_DAYS = 3
    private const val SNAPSHOT_DAYS = 7
    private const val MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&hydrate=team,linescore"
    private const val ESPN_MLB_LIVE_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    private const val ESPN_FOOTBALL_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

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
            val canonical = runCatching { CanonicalScheduleProvider.load(null, SNAPSHOT_DAYS) }.getOrDefault(emptyList())
            val mlb = runCatching { loadMlbSchedule(SNAPSHOT_DAYS) }.getOrDefault(emptyList())
            // NCAA FB is a critical active-season league. Always merge a direct ESPN
            // seven-day snapshot so a malformed/empty canonical feed cannot hide it.
            val ncaaFootball = runCatching { loadEspnNcaaFootballSchedule(SNAPSHOT_DAYS) }.getOrDefault(emptyList())
            val normalized = normalize(canonical + mlb + ncaaFootball)
            if (normalized.isNotEmpty()) {
                snapshotCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else again?.events.orEmpty()
        }
    }

    suspend fun upcoming(league: String? = null, force: Boolean = false): List<SportsEvent> {
        val canonical = league?.let(SportsScheduleService::canonicalLeagueFor)
        val now = Instant.now()
        val cutoff = now.plus(UI_DAYS.toLong(), ChronoUnit.DAYS)
        return all(force).asSequence()
            .filter { !it.isLive }
            .filter { event -> canonical == null || SportsScheduleService.canonicalLeagueFor(event.league) == canonical }
            .filter { event ->
                val start = runCatching { Instant.parse(event.startUtc) }.getOrNull() ?: return@filter false
                val localDate = start.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val today = now.atZone(java.time.ZoneId.systemDefault()).toLocalDate()
                val dateOnly = event.startUtc.matches(Regex(".*T00:00:00(?:\\.000)?Z$"))
                val dateOnlyInWindow = dateOnly && !localDate.isBefore(today) && localDate.isBefore(today.plusDays(UI_DAYS.toLong()))
                dateOnlyInWindow || (!start.isBefore(now.minus(10, ChronoUnit.MINUTES)) && start.isBefore(cutoff))
            }
            .sortedBy { it.startUtc }
            .toList()
    }

    suspend fun live(force: Boolean = false): List<SportsEvent> {
        val cached = liveCache
        if (!force && cached != null && age(cached) < LIVE_TTL_MS) return cached.events
        return liveMutex.withLock {
            val again = liveCache
            if (!force && again != null && age(again) < LIVE_TTL_MS) return@withLock again.events
            val feedLive = runCatching { CanonicalScheduleProvider.load(null, 1) }.getOrDefault(emptyList()).filter { it.isLive }
            val mlbLive = runCatching { loadMlbSchedule(1, includePreviousUtcDay = true).filter { it.isLive } }.getOrDefault(emptyList())
            val espnMlbLive = runCatching { loadEspnMlbLive() }.getOrDefault(emptyList())
            val ncaaFootballLive = runCatching { loadEspnNcaaFootballSchedule(1).filter { it.isLive } }.getOrDefault(emptyList())
            val normalized = normalize(feedLive + mlbLive + espnMlbLive + ncaaFootballLive).filter { it.isLive }
            if (normalized.isNotEmpty()) {
                liveCache = CachedEvents(normalized, System.currentTimeMillis())
                normalized
            } else again?.events.orEmpty()
        }
    }

    private suspend fun loadMlbSchedule(daysAhead: Int, includePreviousUtcDay: Boolean = false): List<SportsEvent> = withContext(Dispatchers.IO) {
        val todayUtc = LocalDate.now(ZoneOffset.UTC)
        val startDate = if (includePreviousUtcDay) todayUtc.minusDays(1) else todayUtc
        val endDate = if (includePreviousUtcDay) todayUtc else todayUtc.plusDays(daysAhead.toLong().coerceAtLeast(1L) - 1L)
        val url = "$MLB_SCHEDULE_URL&startDate=$startDate&endDate=$endDate"
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 1_500; c.readTimeout = 2_500; c.requestMethod = "GET"; c.instanceFollowRedirects = true; c.useCaches = false
        c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0"); c.setRequestProperty("Pragma", "no-cache"); c.setRequestProperty("User-Agent", "XSportsX/2.2 Android")
        return@withContext try {
            if (c.responseCode !in 200..299) return@withContext emptyList()
            val dates = JSONObject(c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }).optJSONArray("dates") ?: return@withContext emptyList()
            val out = ArrayList<SportsEvent>()
            for (i in 0 until dates.length()) {
                val games = dates.optJSONObject(i)?.optJSONArray("games") ?: continue
                for (j in 0 until games.length()) {
                    val game = games.optJSONObject(j) ?: continue; val status = game.optJSONObject("status") ?: continue
                    val abstractState = status.optString("abstractGameState").lowercase(); val detailedState = status.optString("detailedState").lowercase()
                    val live = abstractState == "live" || abstractState == "in progress" || detailedState == "live" || detailedState.contains("in progress")
                    val final = abstractState == "final" || detailedState == "final" || detailedState.contains("game over")
                    val teams = game.optJSONObject("teams") ?: continue; val awayTeam = teams.optJSONObject("away")?.optJSONObject("team"); val homeTeam = teams.optJSONObject("home")?.optJSONObject("team")
                    val away = awayTeam?.optString("name").orEmpty(); val home = homeTeam?.optString("name").orEmpty(); val start = game.optString("gameDate")
                    if (away.isBlank() || home.isBlank() || start.isBlank()) continue
                    val gamePk = game.optLong("gamePk", 0L)
                    out += SportsEvent(if (gamePk > 0) "mlb-$gamePk" else "mlb-${start.take(16)}-$away-$home", "Baseball", "MLB", "$away @ $home", start,
                        when { live -> "LIVE"; final -> "FINAL"; else -> "UPCOMING" }, when { live -> "in"; final -> "post"; else -> "pre" }, home, away,
                        homeTeam?.optString("link").orEmpty(), awayTeam?.optString("link").orEmpty(), sourceUrl = if (gamePk > 0) "https://www.mlb.com/gameday/$gamePk" else "https://www.mlb.com/scores")
                }
            }
            out
        } finally { c.disconnect() }
    }

    /** Direct ESPN FBS/FCS schedule for the current window; independent of the repo feed. */
    private suspend fun loadEspnNcaaFootballSchedule(daysAhead: Int): List<SportsEvent> = withContext(Dispatchers.IO) {
        val start = LocalDate.now(ZoneOffset.UTC); val end = start.plusDays(daysAhead.toLong().coerceAtLeast(1L) - 1L)
        val dateRange = "${start.toString().replace("-", "")}-${end.toString().replace("-", "")}"
        val out = ArrayList<SportsEvent>()
        for ((league, group) in listOf("NCAA FB" to null, "NCAA FCS" to "81")) {
            val target = "$ESPN_FOOTBALL_URL?dates=$dateRange&limit=1000" + if (group != null) "&groups=$group" else ""
            val c = runCatching { URL(target).openConnection() as HttpURLConnection }.getOrNull() ?: continue
            c.connectTimeout = 1_500; c.readTimeout = 3_500; c.requestMethod = "GET"; c.instanceFollowRedirects = true; c.useCaches = false
            c.setRequestProperty("Accept", "application/json"); c.setRequestProperty("Cache-Control", "no-cache, no-store, max-age=0"); c.setRequestProperty("Pragma", "no-cache"); c.setRequestProperty("User-Agent", "XSportsX/2.3 Android")
            try {
                if (c.responseCode !in 200..299) continue
                val events = JSONObject(c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }).optJSONArray("events") ?: continue
                for (i in 0 until events.length()) {
                    val event = events.optJSONObject(i) ?: continue; val competition = event.optJSONArray("competitions")?.optJSONObject(0) ?: continue; val competitors = competition.optJSONArray("competitors") ?: continue
                    var home=""; var away=""; var homeLogo=""; var awayLogo=""
                    for (j in 0 until competitors.length()) {
                        val item = competitors.optJSONObject(j) ?: continue; val team = item.optJSONObject("team") ?: continue; val name = team.optString("displayName").ifBlank { team.optString("shortDisplayName") }; val logo = team.optString("logo")
                        if (item.optString("homeAway") == "home") { home=name; homeLogo=logo } else if (item.optString("homeAway") == "away") { away=name; awayLogo=logo }
                    }
                    val startUtc=event.optString("date"); if (home.isBlank() || away.isBlank() || startUtc.isBlank()) continue
                    val type=competition.optJSONObject("status")?.optJSONObject("type") ?: event.optJSONObject("status")?.optJSONObject("type")
                    val state=type?.optString("state").orEmpty().lowercase(); val detail=type?.optString("detail").orEmpty().lowercase(); val live=state=="in" || detail.contains("in progress") || detail.contains("live"); val final=state=="post" || detail.contains("final") || detail.contains("game over")
                    val id=event.optString("id")
                    out += SportsEvent(if (id.isBlank()) "${league.lowercase().replace(' ','-')}-${startUtc.take(16)}-$away-$home" else "${league.lowercase().replace(' ','-')}-espn-$id", "Football", league, "$away @ $home", startUtc,
                        when { live -> "LIVE"; final -> "FINAL"; else -> "UPCOMING" }, when { live -> "in"; final -> "post"; else -> "pre" }, home, away, homeLogo, awayLogo,
                        sourceUrl = if (id.isBlank()) "https://www.espn.com/college-football/scoreboard" else "https://www.espn.com/college-football/game/_/gameId/$id")
                }
            } finally { c.disconnect() }
        }
        out
    }

    private suspend fun loadEspnMlbLive(): List<SportsEvent> = withContext(Dispatchers.IO) {
        val todayUtc=LocalDate.now(ZoneOffset.UTC); val dates=listOf(todayUtc.minusDays(1),todayUtc).distinct(); val out=ArrayList<SportsEvent>()
        for (date in dates) {
            val target="$ESPN_MLB_LIVE_URL?dates=${date.toString().replace("-","")}&limit=1000"; val c=URL(target).openConnection() as HttpURLConnection
            c.connectTimeout=1_500; c.readTimeout=2_500; c.requestMethod="GET"; c.instanceFollowRedirects=true; c.useCaches=false; c.setRequestProperty("Accept","application/json"); c.setRequestProperty("Cache-Control","no-cache, no-store, max-age=0"); c.setRequestProperty("Pragma","no-cache"); c.setRequestProperty("User-Agent","XSportsX/2.2 Android")
            try {
                if(c.responseCode !in 200..299) continue
                val events=JSONObject(c.inputStream.bufferedReader(Charsets.UTF_8).use{it.readText()}).optJSONArray("events")?:continue
                for(i in 0 until events.length()){
                    val event=events.optJSONObject(i)?:continue; val competition=event.optJSONArray("competitions")?.optJSONObject(0)?:continue; val status=competition.optJSONObject("status")?.optJSONObject("type")?:event.optJSONObject("status")?.optJSONObject("type")?:continue; val state=status.optString("state").lowercase(); val detail=status.optString("detail").lowercase(); if(!(state=="in"||detail.contains("in progress")||detail.contains("live")))continue
                    val competitors=competition.optJSONArray("competitors")?:continue; var home="";var away="";var homeLogo="";var awayLogo=""
                    for(j in 0 until competitors.length()){val team=competitors.optJSONObject(j)?:continue;val obj=team.optJSONObject("team")?:continue;val name=obj.optString("shortDisplayName").ifBlank{obj.optString("displayName")};val logo=obj.optString("logo");if(team.optString("homeAway")=="home"){home=name;homeLogo=logo}else if(team.optString("homeAway")=="away"){away=name;awayLogo=logo}}
                    val start=event.optString("date");if(home.isBlank()||away.isBlank()||start.isBlank())continue;val id=event.optString("id");out+=SportsEvent(if(id.isBlank())"espn-mlb-${start.take(16)}-$away-$home" else "espn-mlb-$id","Baseball","MLB","$away @ $home",start,"LIVE","in",home,away,homeLogo,awayLogo,sourceUrl=if(id.isBlank())"https://www.espn.com/mlb/scoreboard" else "https://www.espn.com/mlb/game/_/gameId/$id")
                }
            }finally{c.disconnect()}
        }
        out
    }

    fun clear() { snapshotCache=null; liveCache=null }
    private fun age(cache: CachedEvents): Long = System.currentTimeMillis()-cache.loadedAtMs
    private fun normalize(events: List<SportsEvent>): List<SportsEvent> { val seen=LinkedHashSet<String>(); return events.map{it.copy(league=SportsScheduleService.canonicalLeagueFor(it.league))}.filter{seen.add(eventKey(it))}.sortedWith(compareBy<SportsEvent>{!(it.isLive||it.isPregame())}.thenBy{it.startUtc}) }
    private fun eventKey(event: SportsEvent): String { fun clean(value:String)=value.lowercase().replace(Regex("[^a-z0-9]+")," ").trim().replace(Regex("\\s+")," "); val teams=listOf(clean(event.away),clean(event.home)).sorted(); val matchup=if(teams.any{it.isNotBlank()})teams.joinToString("|") else clean(event.title); return "${clean(event.league)}|$matchup|${event.startUtc.take(16)}" }
}
