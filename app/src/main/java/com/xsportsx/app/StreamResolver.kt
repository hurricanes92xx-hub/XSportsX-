package com.xsportsx.app

import android.content.Context
import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.BufferedInputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.ConcurrentHashMap
import java.util.zip.GZIPInputStream

data class ResolvedStream(val name: String, val group: String, val url: String, val iconUrl: String = "")
private data class StreamCacheEntry(val streams: List<ResolvedStream>, val loadedAt: Long)
private data class EventStreamCacheEntry(val streams: List<ResolvedStream>, val loadedAt: Long)

class StreamResolver(context: Context) {
    private val store = SourceStore(context.applicationContext)
    private val publicHealthIndex = PublicSourceHealthIndex(context.applicationContext)
    private val publicResolver = PublicSourceResolver()
    private val publicEventMatcher = PublicEventMatcher(publicResolver)
    private val eventInFlight = ConcurrentHashMap<String, kotlinx.coroutines.Deferred<List<ResolvedStream>>>()
    companion object {
        private const val CACHE_TTL_MS = 10 * 60 * 1000L
        private const val EVENT_CACHE_TTL_MS = 2 * 60 * 1000L
        private val cache = LruCache<String, StreamCacheEntry>(2)
        private val eventCache = LruCache<String, EventStreamCacheEntry>(32)
        private val cacheMutex = Mutex()
        private val eventCacheMutex = Mutex()
        fun invalidateCache() { cache.evictAll(); eventCache.evictAll() }
    }

    suspend fun preloadLiveStreams(force: Boolean = false): Int = withContext(Dispatchers.IO) {
        val config = store.load(); val key = cacheKey(config); val now = System.currentTimeMillis()
        cache.get(key)?.let { if (!force && now - it.loadedAt < CACHE_TTL_MS) return@withContext it.streams.size }
        val streams = cacheMutex.withLock {
            val fresh = cache.get(key)
            if (!force && fresh != null && System.currentTimeMillis() - fresh.loadedAt < CACHE_TTL_MS) fresh.streams
            else {
                val privateStreams = if (config.isConfigured()) { if (config.type == "M3U") loadM3u(config.m3uUrl) else loadXtream(config) } else emptyList()
                val publicStreams = runCatching { publicResolver.load(force) }.getOrDefault(emptyList()).map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) }
                val merged = dedupe(privateStreams + publicStreams)
                cache.put(key, StreamCacheEntry(merged, System.currentTimeMillis())); merged
            }
        }
        streams.size
    }

    suspend fun loadLiveStreams(force: Boolean = false): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load(); val key = cacheKey(config); val now = System.currentTimeMillis()
        cache.get(key)?.takeIf { !force && now - it.loadedAt < CACHE_TTL_MS }?.streams?.let { return@withContext it }
        preloadLiveStreams(force); cache.get(key)?.streams.orEmpty()
    }

    suspend fun loadMatchingStreams(filter: String?, force: Boolean = false): List<ResolvedStream> {
        val all = loadLiveStreams(force); val terms = filter?.split("||")?.map { it.trim() }?.filter { it.length >= 3 }.orEmpty()
        if (terms.isEmpty()) return all
        return all.filter { stream -> val haystack = (stream.name + " " + stream.group).lowercase(); terms.any { haystack.contains(it.lowercase()) } }
    }

    suspend fun loadMatchingEventStreams(event: SportsEvent, force: Boolean = false): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load()
        val eventKey = eventCacheKey(config, event)
        val now = System.currentTimeMillis()
        if (!force) {
            eventCache.get(eventKey)?.takeIf { now - it.loadedAt < EVENT_CACHE_TTL_MS }?.streams?.let { return@withContext it }
        }

        // Single-flight protection: concurrent clicks on the same live event now
        // share one resolver operation instead of launching duplicate public
        // discovery/health work. Different events remain fully concurrent.
        val existing = eventInFlight[eventKey]
        if (existing != null) return@withContext existing.await()

        coroutineScope {
            val work = async(Dispatchers.IO) {
                resolveEventStreams(config, eventKey, event, force)
            }
            val winner = eventInFlight.putIfAbsent(eventKey, work) ?: work
            try {
                winner.await()
            } finally {
                if (winner === work) eventInFlight.remove(eventKey, work)
            }
        }
    }

    private suspend fun resolveEventStreams(config: SourceConfig, eventKey: String, event: SportsEvent, force: Boolean): List<ResolvedStream> {
        // Recheck after becoming the single in-flight owner so a racing caller
        // can never repeat a freshly completed event resolution.
        if (!force) {
            val now = System.currentTimeMillis()
            eventCache.get(eventKey)?.takeIf { now - it.loadedAt < EVENT_CACHE_TTL_MS }?.streams?.let { return it }
        }

        val privateMatches = if (config.isConfigured()) {
            val private = if (config.type == "M3U") loadM3u(config.m3uUrl) else loadXtream(config)
            matchEventAgainstStreams(event, private)
        } else emptyList()

        // Fast path: reuse public candidates that were already health-checked for
        // this exact event, league, sport, or broadcast network. This avoids a
        // full public discovery pass on every click.
        val indexed = publicHealthIndex.rankResolved(
            eventId = event.id,
            sport = event.sport,
            league = event.league,
            network = event.broadcast,
            limit = 8
        ).map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) }

        // Cold/warm discovery path: only run the existing event matcher when the
        // index does not already have enough candidates, or when explicitly forced.
        val discovered = if (force || indexed.size < 2) {
            runCatching { publicEventMatcher.find(event, force) }.getOrDefault(emptyList())
        } else emptyList()

        // Feed successfully health-checked discoveries back into the persistent
        // index so future clicks become progressively faster.
        discovered.forEach { publicHealthIndex.record(it, event.sport, event.league, event.id, event.broadcast, true) }

        val publicMatches = (indexed + discovered.map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) })
        val officialVideo = event.youtubeVideoId.trim().takeIf { it.matches(Regex("[A-Za-z0-9_-]{11}")) }?.let {
            ResolvedStream("${event.title.ifBlank { "Official event" }} • YouTube", "OFFICIAL VIDEO", "https://www.youtube.com/watch?v=$it")
        }
        val resolved = dedupe(listOfNotNull(officialVideo) + privateMatches + publicMatches)
        eventCacheMutex.withLock {
            eventCache.put(eventKey, EventStreamCacheEntry(resolved, System.currentTimeMillis()))
        }
        resolved
    }

    private fun matchEventAgainstStreams(event: SportsEvent, streams: List<ResolvedStream>): List<ResolvedStream> {
        val eventTerms = listOf(event.title, event.home, event.away, event.league, event.broadcast).map { normalize(it) }.filter { it.length >= 3 }
        if (eventTerms.isEmpty()) return emptyList()
        return streams.mapNotNull { stream -> val haystack = normalize("${stream.name} ${stream.group}"); val hits = eventTerms.count { term -> haystack.contains(term) }; if (hits == 0) null else hits to stream }
            .sortedByDescending { it.first }.map { it.second }.take(12)
    }

    private fun normalize(value: String): String = value.lowercase().replace("&", " and ").replace(Regex("[^a-z0-9+]+"), " ").trim().replace(Regex("\\s+"), " ")
    private fun cacheKey(config: SourceConfig): String = listOf(config.type, config.server.trim().removeSuffix("/"), config.username, config.m3uUrl, BuildConfig.PAIRING_BASE_URL).joinToString("|")
    private fun eventCacheKey(config: SourceConfig, event: SportsEvent): String = listOf(cacheKey(config), event.id, event.title, event.home, event.away, event.league, event.broadcast).joinToString("|")
    private fun dedupe(streams: List<ResolvedStream>): List<ResolvedStream> { val seen = HashSet<String>(); return streams.filter { seen.add(it.url) } }

    private fun loadXtream(config: SourceConfig): List<ResolvedStream> {
        val base = config.server.trim().removeSuffix("/"); val query = "username=${enc(config.username)}&password=${enc(config.password)}"; val array = JSONArray(http("$base/player_api.php?$query&action=get_live_streams")); val result = ArrayList<ResolvedStream>(array.length())
        for (i in 0 until array.length()) { val o = array.optJSONObject(i) ?: continue; val id = o.optString("stream_id"); val name = o.optString("name").trim(); if (id.isBlank() || name.isBlank()) continue; val category = o.optString("category_name").ifBlank { "LIVE" }; val icon = o.optString("stream_icon"); val hls = "$base/live/${enc(config.username)}/${enc(config.password)}/$id.m3u8"; result += ResolvedStream(name, category, hls, icon) }
        return result
    }

    private fun loadM3u(url: String): List<ResolvedStream> {
        val result = ArrayList<ResolvedStream>(); var name = ""; var group = "LIVE"; var icon = ""
        for (line in http(url).lineSequence()) { val trimmed = line.trim(); when { trimmed.startsWith("#EXTINF", true) -> { name = trimmed.substringAfterLast(',', "Unnamed").trim(); group = attr(trimmed, "group-title").ifBlank { "LIVE" }; icon = attr(trimmed, "tvg-logo") }; trimmed.isNotBlank() && !trimmed.startsWith("#") -> { if (name.isNotBlank()) result += ResolvedStream(name, group, trimmed, icon); name = ""; group = "LIVE"; icon = "" } } }
        return result
    }

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply { requestMethod = "GET"; connectTimeout = 5000; readTimeout = 15000; instanceFollowRedirects = true; useCaches = true; setRequestProperty("User-Agent", "XSportsX/2.0"); setRequestProperty("Accept", "application/json, text/plain, */*"); setRequestProperty("Accept-Encoding", "gzip"); setRequestProperty("Connection", "keep-alive") }
        return try { val code = c.responseCode; if (code !in 200..299) error("Source returned HTTP $code"); val raw: InputStream = BufferedInputStream(c.inputStream); val input = if (c.contentEncoding?.contains("gzip", true) == true) GZIPInputStream(raw) else raw; input.bufferedReader(Charsets.UTF_8).use { it.readText() } } finally { c.disconnect() }
    }
    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
    private fun attr(line: String, key: String): String { val regex = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE); return regex.find(line)?.groupValues?.getOrNull(1).orEmpty() }
}
