package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.channels.Channel
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.ConcurrentHashMap
import java.util.zip.GZIPInputStream

/**
 * Fast Xtream metadata index. Categories are fetched first; event resolution never
 * downloads the provider's full live catalog. Cached category indexes are preferred.
 */
class XtreamSourceIndex(context: Context) {
    data class Category(val id: String, val name: String)
    data class Channel(val id: String, val name: String, val categoryId: String, val group: String, val icon: String)

    private val prefs = context.applicationContext.getSharedPreferences("xsportsx_xtream_index", Context.MODE_PRIVATE)
    private val categoryCache = ConcurrentHashMap<String, List<Category>>()
    private val channelCache = ConcurrentHashMap<String, List<Channel>>()
    private val running = ConcurrentHashMap<String, Boolean>()

    companion object {
        private const val CATEGORY_TTL = 6 * 60 * 60 * 1000L
        private const val INDEX_TTL = 30 * 60 * 1000L
        private const val CATEGORY_CALL_TIMEOUT_MS = 3_000
        private const val MAX_EVENT_CATEGORIES = 12
        private val SPORTS_TERMS = setOf(
            "sport", "sports", "espn", "fox", "fs1", "fs2", "cbs sport", "nfl", "mlb", "nba", "nhl",
            "ncaa", "college", "sec", "acc", "big ten", "btn", "tnt", "tbs", "trutv", "usa sport",
            "wwe", "aew", "tna", "wrestling", "ufc", "fight", "boxing", "dazn", "tsn", "sportsnet",
            "paramount", "peacock", "fubo", "fanduel", "golf", "tennis", "nascar", "racing", "soccer", "football",
            "hockey", "baseball", "basketball", "motorsport", "bein", "tudn", "volleyball", "field hockey"
        )
        private val BROADCAST_CATEGORY_TERMS = setOf(
            "espn", "espn2", "espn 2", "espnu", "espn u", "espn plus", "espn+", "abc",
            "cbs", "cbs sports", "cbs sports network", "fox", "fox sports", "fs1", "fs2",
            "nbc", "peacock", "sec network", "secn", "secn+", "acc network", "accn", "accnx",
            "big ten network", "btn", "tnt", "tbs", "trutv", "tru tv", "nfl network", "nba tv",
            "mlb network", "nhl network", "paramount", "paramount+", "paramount plus", "tudn", "telemundo",
            "univision", "fanduel sports network", "fanduel", "the cw", "cw sports"
        )
    }

    /**
     * Event-first resolution. It searches only relevant Xtream categories and does
     * the category requests concurrently. Cached categories are used immediately,
     * but insufficient cached matches never prevent a deeper provider search.
     */
    suspend fun fastResolve(
        config: SourceConfig,
        event: SportsEvent,
        maxCategories: Int = MAX_EVENT_CATEGORIES,
        stopWhen: ((List<Channel>) -> Boolean)? = null
    ): List<Channel> {
        if (!config.isConfigured() || config.type != "XTREAM") return emptyList()
        val categories = getCategories(config, force = false)
        val ranked = categories.map { it to categoryScore(it.name, event) }
            .filter { it.second > 0 }
            .sortedByDescending { it.second }
            .take(maxCategories)
            .map { it.first }
        if (ranked.isEmpty()) return emptyList()

        return coroutineScope {
            val found = LinkedHashMap<String, Channel>()
            val uncached = ArrayList<Pair<Int, Category>>()

            ranked.forEachIndexed { index, category ->
                val key = sourceKey(config) + ":" + category.id
                val cached = channelCache[key] ?: loadPersistedChannels(key).orEmpty()
                if (cached.isNotEmpty()) {
                    cached.forEach { found[it.id] = it }
                } else {
                    uncached += index to category
                }
            }

            if (stopWhen?.invoke(found.values.toList()) == true) {
                return@coroutineScope found.values.toList()
            }
            if (uncached.isEmpty()) return@coroutineScope found.values.toList()

            val results = Channel<Pair<Int, List<Channel>>>(capacity = uncached.size.coerceAtLeast(1))
            val jobs = uncached.map { (index, category) ->
                launch(Dispatchers.IO) {
                    val channels = runCatching {
                        getCategoryChannelsBlocking(config, category.id, force = false)
                    }.getOrDefault(emptyList())
                    results.send(index to channels)
                }
            }

            repeat(uncached.size) {
                val (_, channels) = results.receive()
                channels.forEach { found[it.id] = it }
                if (stopWhen?.invoke(found.values.toList()) == true) {
                    jobs.forEach { it.cancel() }
                    return@coroutineScope found.values.toList()
                }
            }
            found.values.toList()
        }
    }

    /** Cached sports/broadcast categories and channels for startup; no network work. */
    fun getCachedSports(config: SourceConfig): List<Channel> {
        if (!config.isConfigured() || config.type != "XTREAM") return emptyList()
        val categories = categoryCache[sourceKey(config)] ?: loadPersistedCategories(sourceKey(config)).orEmpty()
        val key = sourceKey(config)
        return categories.filter { categoryScore(it.name, null) > 0 }
            .flatMap { channelCache["$key:${it.id}"] ?: loadPersistedChannels("$key:${it.id}").orEmpty() }
            .distinctBy { it.id }
    }

    fun warm(config: SourceConfig) {
        if (!config.isConfigured() || config.type != "XTREAM") return
        val key = sourceKey(config)
        if (running.putIfAbsent("all:$key", true) != null) return
        Thread {
            try {
                val categories = getCategoriesBlocking(config, false)
                categories.filter { categoryScore(it.name, null) > 0 }
                    .sortedByDescending { categoryScore(it.name, null) }
                    .take(32)
                    .forEach { getCategoryChannelsBlocking(config, it.id, false) }
            } catch (_: Throwable) {
            } finally {
                running.remove("all:$key")
            }
        }.start()
    }

    fun getCachedAll(config: SourceConfig): List<Channel> = getCachedSports(config)

    private suspend fun getCategories(config: SourceConfig, force: Boolean): List<Category> = getCategoriesBlocking(config, force)

    private fun getCategoriesBlocking(config: SourceConfig, force: Boolean): List<Category> {
        val key = sourceKey(config)
        categoryCache[key]?.let { if (!force) return it }
        val savedAt = prefs.getLong("cat_time_$key", 0L)
        if (!force && System.currentTimeMillis() - savedAt < CATEGORY_TTL) {
            loadPersistedCategories(key)?.let { categoryCache[key] = it; return it }
        }
        val query = authQuery(config)
        val array = JSONArray(http("${config.server.trim().removeSuffix("/")}/player_api.php?$query&action=get_live_categories"))
        val result = ArrayList<Category>(array.length())
        for (i in 0 until array.length()) {
            val o = array.optJSONObject(i) ?: continue
            val id = o.optString("category_id").trim()
            val name = o.optString("category_name").trim()
            if (id.isNotBlank() && name.isNotBlank()) result += Category(id, name)
        }
        categoryCache[key] = result
        persistCategories(key, result)
        return result
    }

    private fun getCategoryChannelsBlocking(config: SourceConfig, categoryId: String, force: Boolean): List<Channel> {
        val key = sourceKey(config) + ":" + categoryId
        channelCache[key]?.let { if (!force) return it }
        val savedAt = prefs.getLong("stream_time_$key", 0L)
        if (!force && System.currentTimeMillis() - savedAt < INDEX_TTL) {
            loadPersistedChannels(key)?.let { channelCache[key] = it; return it }
        }
        val query = authQuery(config)
        val url = "${config.server.trim().removeSuffix("/")}/player_api.php?$query&action=get_live_streams&category_id=${enc(categoryId)}"
        val array = JSONArray(http(url))
        val result = ArrayList<Channel>(array.length())
        for (i in 0 until array.length()) {
            val o = array.optJSONObject(i) ?: continue
            val id = o.optString("stream_id").trim()
            val name = o.optString("name").trim()
            if (id.isBlank() || name.isBlank()) continue
            val group = o.optString("category_name").ifBlank { categoryId }
            result += Channel(id, name, o.optString("category_id").ifBlank { categoryId }, group, o.optString("stream_icon"))
        }
        channelCache[key] = result
        persistChannels(key, result)
        return result
    }

    private fun categoryScore(name: String, event: SportsEvent?): Int {
        val n = normalize(name)
        if (n.isBlank()) return 0
        var score = 0
        SPORTS_TERMS.forEach { if (n.contains(normalize(it))) score += 10 }
        BROADCAST_CATEGORY_TERMS.forEach { if (n.contains(normalize(it))) score += 18 }
        if (event != null) {
            listOf(event.sport, event.league, event.broadcast).forEach { term ->
                val t = normalize(term)
                if (t.length >= 3 && n.contains(t)) score += 25
            }
            val eventTerms = normalize("${event.sport} ${event.league} ${event.broadcast} ${event.title}")
            if (eventTerms.contains("wwe") && n.contains("wrestling")) score += 25
            if (eventTerms.contains("ufc") && (n.contains("ufc") || n.contains("fight"))) score += 25
            if (eventTerms.contains("volleyball") && n.contains("volleyball")) score += 30
            if (eventTerms.contains("field hockey") && n.contains("hockey")) score += 30
            if (eventTerms.contains("ncaa") || eventTerms.contains("college") || eventTerms.contains("university")) {
                listOf("espn", "abc", "cbs", "fox", "fs1", "sec network", "secn", "acc network", "accn", "big ten network", "btn")
                    .forEach { if (n.contains(it)) score += 12 }
            }
        }
        return score
    }

    private fun sourceKey(config: SourceConfig): String = sha1("${config.server}|${config.username}")
    private fun authQuery(config: SourceConfig): String = "username=${enc(config.username)}&password=${enc(config.password)}"
    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
    private fun normalize(value: String): String = value.lowercase().replace("+", " plus ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")

    private fun persistCategories(key: String, values: List<Category>) {
        val a = JSONArray(); values.forEach { a.put(JSONObject().put("id", it.id).put("name", it.name)) }
        prefs.edit().putString("cat_$key", a.toString()).putLong("cat_time_$key", System.currentTimeMillis()).apply()
    }

    private fun loadPersistedCategories(key: String): List<Category>? = runCatching {
        val a = JSONArray(prefs.getString("cat_$key", "[]")); buildList { for (i in 0 until a.length()) { val o = a.optJSONObject(i) ?: continue; add(Category(o.optString("id"), o.optString("name"))) } }
    }.getOrNull()?.takeIf { it.isNotEmpty() }

    private fun persistChannels(key: String, values: List<Channel>) {
        val a = JSONArray(); values.forEach { a.put(JSONObject().put("id", it.id).put("name", it.name).put("categoryId", it.categoryId).put("group", it.group).put("icon", it.icon)) }
        prefs.edit().putString("streams_$key", a.toString()).putLong("stream_time_$key", System.currentTimeMillis()).apply()
    }

    private fun loadPersistedChannels(key: String): List<Channel>? = runCatching {
        val a = JSONArray(prefs.getString("streams_$key", "[]")); buildList { for (i in 0 until a.length()) { val o = a.optJSONObject(i) ?: continue; add(Channel(o.optString("id"), o.optString("name"), o.optString("categoryId"), o.optString("group"), o.optString("icon"))) } }
    }.getOrNull()?.takeIf { it.isNotEmpty() }

    private fun sha1(value: String): String {
        val bytes = java.security.MessageDigest.getInstance("SHA-1").digest(value.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 2_000
            readTimeout = CATEGORY_CALL_TIMEOUT_MS
            instanceFollowRedirects = true
            useCaches = true
            setRequestProperty("User-Agent", "XSportsX/3.0")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Accept-Encoding", "gzip")
            setRequestProperty("Connection", "keep-alive")
        }
        return try {
            val code = c.responseCode
            if (code !in 200..299) error("Source returned HTTP $code")
            val raw: InputStream = BufferedInputStream(c.inputStream)
            val input = if (c.contentEncoding?.contains("gzip", true) == true) GZIPInputStream(raw) else raw
            input.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }
}