package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.channels.Channel as CoroutineChannel
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
     * the category requests concurrently. Once the caller has enough matching
     * channels, remaining requests are cancelled instead of scanning the provider.
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

        val cached = ranked.flatMap { category ->
            val key = sourceKey(config) + ":" + category.id
            channelCache[key] ?: loadPersistedChannels(key).orEmpty()
        }.distinctBy { it.id }
        if (cached.isNotEmpty()) return cached

        return coroutineScope {
            val results = CoroutineChannel<Pair<Int, List<Channel>>>(capacity = ranked.size.coerceAtLeast(1))
            val jobs = ranked.mapIndexed { index, category ->
                launch(Dispatchers.IO) {
                    val channels = runCatching {
                        getCategoryChannelsBlocking(config, category.id, force = false)
                    }.getOrDefault(emptyList())
                    results.send(index to channels)
                }
            }

            val found = LinkedHashMap<String, Channel>()
            repeat(ranked.size) {
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

    private suspend fun getCategories(config: SourceConfig, force: Boolean): List<Category> =
        getCategoriesBlocking(config, force)

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
