package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/** Cached-first, bounded Xtream event resolver. */
class FastXtreamEventResolver(context: Context) {
    private val store = SourceStore(context.applicationContext)
    private val index = XtreamSourceIndex(context.applicationContext)

    companion object {
        private const val MAX_CATEGORIES = 6
        private const val MAX_MATCHES = 12
        private const val RESOLVE_BUDGET_MS = 2600L
        private const val CONNECT_MS = 700L
        private const val READ_MS = 1600L
        private val HTTP = OkHttpClient.Builder()
            .connectTimeout(CONNECT_MS, TimeUnit.MILLISECONDS)
            .readTimeout(READ_MS, TimeUnit.MILLISECONDS)
            .callTimeout(READ_MS + 700, TimeUnit.MILLISECONDS)
            .retryOnConnectionFailure(false)
            .build()
    }

    suspend fun resolve(event: SportsEvent): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load()
        if (!config.isConfigured() || config.type != "XTREAM") return@withContext emptyList()
        withTimeoutOrNull(RESOLVE_BUDGET_MS) {
            val cached = index.getCachedAll(config)
            match(event, cached.map { toStream(config, it) }).takeIf { it.isNotEmpty() }?.let { return@withTimeoutOrNull it }

            // Cold-cache path: fetch only category metadata, rank likely sports categories,
            // then query those categories concurrently. Never hydrate the entire provider here.
            val categoryIds = fetchCategories(config)
                .map { it.first to categoryScore(it.second, event) }
                .filter { it.second > 0 }
                .sortedByDescending { it.second }
                .take(MAX_CATEGORIES)
                .map { it.first }

            val channels = coroutineScope {
                categoryIds.map { id -> async(Dispatchers.IO) { fetchCategory(config, id) } }
                    .awaitAll().flatten()
            }
            match(event, channels).take(MAX_MATCHES)
        }.orEmpty()
    }

    private fun fetchCategories(config: SourceConfig): List<Pair<String, String>> = runCatching {
        val query = "username=${enc(config.username)}&password=${enc(config.password)}&action=get_live_categories"
        val request = Request.Builder()
            .url("${config.server.trim().removeSuffix("/")}/player_api.php?$query")
            .get().header("User-Agent", "XSportsX/4.0").header("Accept", "application/json").build()
        HTTP.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@use emptyList()
            val body = response.body ?: return@use emptyList()
            val array = JSONArray(body.string())
            buildList {
                for (i in 0 until array.length()) {
                    val o = array.optJSONObject(i) ?: continue
                    val id = o.optString("category_id").trim()
                    val name = o.optString("category_name").trim()
                    if (id.isNotBlank() && name.isNotBlank()) add(id to name)
                }
            }
        }
    }.getOrDefault(emptyList())

    private fun categoryScore(name: String, event: SportsEvent): Int {
        val n = norm(name)
        var score = 0
        val sport = norm(event.sport)
        val league = norm(event.league)
        val broadcast = norm(event.broadcast)
        if (sport.length >= 3 && n.contains(sport)) score += 60
        if (league.length >= 3 && n.contains(league)) score += 70
        if (broadcast.length >= 3 && n.contains(broadcast)) score += 55
        listOf("sport", "sports", "espn", "fox", "cbs", "nbc", "sec", "acc", "big ten", "college", "ncaa", "wwe", "ufc", "boxing", "soccer", "football", "basketball", "baseball", "hockey", "volleyball", "tennis", "golf", "racing").forEach { if (n.contains(norm(it))) score += 8 }
        if (event.league.contains("NCAA", true) && (n.contains("college") || n.contains("ncaa") || n.contains("espn") || n.contains("sec") || n.contains("acc") || n.contains("big ten"))) score += 35
        return score
    }

    private fun fetchCategory(config: SourceConfig, categoryId: String): List<ResolvedStream> = runCatching {
        val query = "username=${enc(config.username)}&password=${enc(config.password)}&action=get_live_streams&category_id=${enc(categoryId)}"
        val request = Request.Builder().url("${config.server.trim().removeSuffix("/")}/player_api.php?$query")
            .get().header("User-Agent", "XSportsX/4.0").header("Accept", "application/json").build()
        HTTP.newCall(request).execute().use { response ->
            if (!response.isSuccessful) return@use emptyList()
            val body = response.body ?: return@use emptyList()
            val array = JSONArray(body.string())
            buildList {
                for (i in 0 until array.length()) {
                    val o = array.optJSONObject(i) ?: continue
                    val id = o.optString("stream_id").trim()
                    val name = o.optString("name").trim()
                    if (id.isBlank() || name.isBlank()) continue
                    add(ResolvedStream(name, o.optString("category_name").ifBlank { categoryId },
                        "${config.server.trim().removeSuffix("/")}/live/${enc(config.username)}/${enc(config.password)}/$id.m3u8",
                        o.optString("stream_icon")))
                }
            }
        }
    }.getOrDefault(emptyList())

    private fun toStream(config: SourceConfig, channel: XtreamSourceIndex.Channel) = ResolvedStream(
        channel.name, channel.group,
        "${config.server.trim().removeSuffix("/")}/live/${enc(config.username)}/${enc(config.password)}/${channel.id}.m3u8",
        channel.icon
    )

    private fun match(event: SportsEvent, streams: List<ResolvedStream>): List<ResolvedStream> {
        if (streams.isEmpty()) return emptyList()
        val teams = terms("${event.home} ${event.away}")
        val league = terms(event.league)
        val broadcast = aliases(event.broadcast)
        return streams.mapNotNull { stream ->
            val hay = norm("${stream.name} ${stream.group}")
            val teamHits = teams.count { it.length >= 4 && hay.contains(it) }
            val leagueHits = league.count { it.length >= 3 && hay.contains(it) }
            val networkHits = broadcast.count { it.length >= 3 && hay.contains(it) }
            val strong = teams.size >= 2 && teamHits >= 2
            val oneTeamWithContext = teamHits >= 1 && (leagueHits > 0 || networkHits > 0)
            val networkOnly = networkHits > 0 && (event.broadcast.isNotBlank() || event.league.contains("NCAA", true))
            if (strong || oneTeamWithContext || networkOnly) (teamHits * 50 + leagueHits * 8 + networkHits * 15) to stream else null
        }.sortedByDescending { it.first }.map { it.second }.distinctBy { it.url }.take(MAX_MATCHES)
    }

    private fun terms(value: String) = norm(value).split(' ').filter { it.length >= 3 && it !in STOP }.distinct()
    private fun aliases(value: String): List<String> {
        val n = norm(value); if (n.isBlank()) return emptyList()
        val out = linkedSetOf(n)
        if (n.contains("espn plus")) out += listOf("espn", "espn plus", "espn+")
        if (n.contains("espn2")) out += listOf("espn2", "espn 2", "espn")
        if (n.contains("espnu")) out += listOf("espnu", "espn u", "espn")
        if (n.contains("sec network")) out += listOf("sec network", "secn", "sec")
        if (n.contains("acc network")) out += listOf("acc network", "accn", "acc")
        if (n.contains("big ten")) out += listOf("big ten network", "btn", "big ten")
        return out.map(::norm).distinct()
    }
    private fun norm(value: String) = value.lowercase().replace("+", " plus ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
    private fun enc(value: String) = URLEncoder.encode(value, "UTF-8")
    private val STOP = setOf("the", "and", "with", "vs", "versus", "game", "live", "network", "sports")
}
