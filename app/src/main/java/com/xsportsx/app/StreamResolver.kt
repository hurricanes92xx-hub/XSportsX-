package com.xsportsx.app

import android.content.Context
import android.util.LruCache
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
    private val appContext = context.applicationContext
    private val store = SourceStore(appContext)
    private val publicHealthIndex = PublicSourceHealthIndex(appContext)
    private val publicResolver = PublicSourceResolver()
    private val publicEventMatcher = PublicEventMatcher(publicResolver)
    private val channelIndex = ChannelIndex()
    private val preResolvedCache = PreResolvedStreamCache(appContext)
    private val xtreamIndex = XtreamSourceIndex(appContext)
    private val m3uIndex = M3uSourceIndex(appContext)
    private val eventInFlight = ConcurrentHashMap<String, Deferred<List<ResolvedStream>>>()
    private val refreshScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    companion object {
        private const val CACHE_TTL_MS = 10 * 60 * 1000L
        private const val EVENT_CACHE_TTL_MS = 2 * 60 * 1000L
        private val cache = LruCache<String, StreamCacheEntry>(2)
        private val eventCache = LruCache<String, EventStreamCacheEntry>(32)
        private val cacheMutex = Mutex(); private val eventCacheMutex = Mutex()
        fun invalidateCache() { cache.evictAll(); eventCache.evictAll() }
    }

    suspend fun preloadLiveStreams(force: Boolean = false): Int = withContext(Dispatchers.IO) {
        val config = store.load(); val key = cacheKey(config)
        cache.get(key)?.let { if (!force && System.currentTimeMillis() - it.loadedAt < CACHE_TTL_MS) { channelIndex.rebuild(it.streams); return@withContext it.streams.size } }
        val streams = cacheMutex.withLock {
            val fresh = cache.get(key)
            if (!force && fresh != null && System.currentTimeMillis() - fresh.loadedAt < CACHE_TTL_MS) fresh.streams
            else coroutineScope {
                val privateDeferred: Deferred<List<ResolvedStream>> = async(Dispatchers.IO) {
                    if (!config.isConfigured()) emptyList()
                    else runCatching {
                        if (config.type == "M3U") {
                            val indexed = m3uIndex.get(config.m3uUrl, allowStale = !force)
                            if (indexed.isNotEmpty() && !force) indexed else loadM3u(config.m3uUrl).also { m3uIndex.put(config.m3uUrl, it) }
                        } else {
                            xtreamIndex.getCachedAll(config).map { c ->
                                ResolvedStream(c.name, c.group, "${config.server.trim().removeSuffix("/")}/live/${enc(config.username)}/${enc(config.password)}/${c.id}.m3u8", c.icon)
                            }.also { xtreamIndex.warm(config) }
                        }
                    }.getOrDefault(emptyList())
                }
                val publicDeferred: Deferred<List<ResolvedStream>> = async(Dispatchers.IO) {
                    runCatching { publicResolver.load(force) }.getOrDefault(emptyList()).map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) }
                }
                val merged = dedupe(privateDeferred.await() + publicDeferred.await())
                cache.put(key, StreamCacheEntry(merged, System.currentTimeMillis())); merged
            }
        }
        channelIndex.rebuild(streams); streams.size
    }

    suspend fun loadLiveStreams(force: Boolean = false): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load(); val key = cacheKey(config)
        cache.get(key)?.takeIf { !force && System.currentTimeMillis() - it.loadedAt < CACHE_TTL_MS }?.streams?.let { channelIndex.rebuild(it); return@withContext it }
        preloadLiveStreams(force); cache.get(key)?.streams.orEmpty().also { channelIndex.rebuild(it) }
    }

    suspend fun loadMatchingStreams(filter: String?, force: Boolean = false): List<ResolvedStream> {
        val all = loadLiveStreams(force); val terms = filter?.split("||")?.map { it.trim() }?.filter { it.length >= 3 }.orEmpty()
        if (terms.isEmpty()) return all
        val indexed = terms.flatMap { channelIndex.find(it, 16) }.distinctBy { it.url }
        return if (indexed.isNotEmpty()) indexed else all.filter { stream -> val haystack = normalize("${stream.name} ${stream.group} ${stream.url}"); terms.any { haystack.contains(normalize(it)) } }
    }

    suspend fun loadMatchingEventStreams(event: SportsEvent, force: Boolean = false): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load(); val eventKey = eventCacheKey(config, event); val canonicalEventId = EventIdentity.id(event); val now = System.currentTimeMillis()
        if (!force) {
            eventCache.get(eventKey)?.takeIf { now - it.loadedAt < EVENT_CACHE_TTL_MS }?.let { cached ->
                val valid = matchEventAgainstStreams(event, cached.streams, strict = true); if (valid.isNotEmpty()) return@withContext valid
                eventCache.remove(eventKey)
            }
            preResolvedCache.get(canonicalEventId, allowStale = true, nowMs = now)?.let { cached ->
                val valid = matchEventAgainstStreams(event, cached.candidates.map { it.stream }, strict = true)
                if (valid.isNotEmpty() && now - cached.savedAtMs < PreResolvedStreamCache.FRESH_TTL_MS) return@withContext valid
                if (valid.isNotEmpty()) { refreshScope.launch { loadMatchingEventStreams(event, true) }; return@withContext valid }
            }
        }
        val existing = eventInFlight[eventKey]; if (existing != null) return@withContext existing.await()
        coroutineScope {
            val work = async(Dispatchers.IO) { resolveEventStreams(config, eventKey, event, force) }
            val winner = eventInFlight.putIfAbsent(eventKey, work) ?: work
            try { return@coroutineScope winner.await() } finally { if (winner === work) eventInFlight.remove(eventKey, work) }
        }
    }

    private suspend fun resolveEventStreams(config: SourceConfig, eventKey: String, event: SportsEvent, force: Boolean): List<ResolvedStream> {
        if (!force) eventCache.get(eventKey)?.takeIf { System.currentTimeMillis() - it.loadedAt < EVENT_CACHE_TTL_MS }?.let { cached ->
            val valid = matchEventAgainstStreams(event, cached.streams, strict = true); if (valid.isNotEmpty()) return valid
        }
        val (privateMatches, indexed) = coroutineScope {
            val privateDeferred: Deferred<List<ResolvedStream>> = async(Dispatchers.IO) {
                val candidates: List<ResolvedStream> = when {
                    !config.isConfigured() -> emptyList()
                    config.type == "XTREAM" -> xtreamIndex.fastResolve(config, event, 12).map { c ->
                        ResolvedStream(c.name, c.group, "${config.server.trim().removeSuffix("/")}/live/${enc(config.username)}/${enc(config.password)}/${c.id}.m3u8", c.icon)
                    }
                    else -> m3uIndex.get(config.m3uUrl, allowStale = true)
                }
                val local: List<ResolvedStream> = if (candidates.isEmpty()) channelIndex.find("${event.broadcast} ${event.home} ${event.away}", 32) else emptyList()
                matchEventAgainstStreams(event, candidates + local, strict = true)
            }
            val publicIndexDeferred: Deferred<List<ResolvedStream>> = async(Dispatchers.IO) {
                publicHealthIndex.rankResolved(event.id, event.sport, event.league, event.broadcast, 16).map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) }
            }
            privateDeferred.await() to publicIndexDeferred.await()
        }
        if (config.type == "M3U" && m3uIndex.get(config.m3uUrl, allowStale = true).isEmpty()) refreshScope.launch { runCatching { loadM3u(config.m3uUrl).also { m3uIndex.put(config.m3uUrl, it); channelIndex.rebuild(it) } } }
        if (config.type == "XTREAM") xtreamIndex.warm(config)
        val discovered = if (force || indexed.size < 2) runCatching { publicEventMatcher.find(event, force) }.getOrDefault(emptyList()) else emptyList()
        discovered.forEach { publicHealthIndex.record(it, event.sport, event.league, event.id, event.broadcast, true) }
        val publicMatches = matchEventAgainstStreams(event, indexed + discovered.map { ResolvedStream("${it.name} • ${it.sourceName}", it.group, it.url, it.iconUrl) }, strict = true)
        val officialVideo = event.youtubeVideoId.trim().takeIf { it.matches(Regex("[A-Za-z0-9_-]{11}")) }?.let { ResolvedStream("${event.title.ifBlank { "Official event" }} • YouTube", "OFFICIAL VIDEO", "https://www.youtube.com/watch?v=$it") }
        val resolved = dedupe(listOfNotNull(officialVideo) + privateMatches + publicMatches)
        eventCacheMutex.withLock { eventCache.put(eventKey, EventStreamCacheEntry(resolved, System.currentTimeMillis())) }
        preResolvedCache.put(EventIdentity.id(event), resolved); return resolved
    }

    private fun matchEventAgainstStreams(event: SportsEvent, streams: List<ResolvedStream>, strict: Boolean = false): List<ResolvedStream> {
        if (streams.isEmpty()) return emptyList()
        val titleTerms = splitTerms(event.title); val teamTerms = splitTerms("${event.home} ${event.away}"); val leagueTerms = splitTerms(event.league); val broadcastTerms = broadcastAliases(event.broadcast); val eventIsLive = event.isLive
        data class Scored(val score: Int, val stream: ResolvedStream)
        val scored = streams.mapNotNull { stream ->
            val haystack = normalize("${stream.name} ${stream.group} ${stream.url}"); val teamHits = teamTerms.count { it.length >= 4 && haystack.contains(it) }; val titleHits = titleTerms.count { it.length >= 4 && haystack.contains(it) }; val leagueHits = leagueTerms.count { it.length >= 3 && haystack.contains(it) }; val networkHits = broadcastTerms.count { it.length >= 3 && haystack.contains(it) }
            val hasTeamEvidence = teamTerms.isNotEmpty() && teamHits >= 1; val hasStrongTeamPair = teamTerms.size >= 2 && teamHits >= 2; val hasLeagueOrNetwork = leagueHits > 0 || networkHits > 0; val score = teamHits * 40 + titleHits * 8 + leagueHits * 4 + networkHits * 10 + if (eventIsLive && networkHits > 0) 5 else 0
            val relevant = if (!strict) (teamHits > 0 || titleHits > 0 || networkHits > 0 || leagueHits > 0) else (hasStrongTeamPair || (hasTeamEvidence && hasLeagueOrNetwork))
            if (relevant) Scored(score, stream) else null
        }
        return scored.sortedWith(compareByDescending<Scored> { it.score }.thenBy { it.stream.name.lowercase() }).map { it.stream }.take(12)
    }

    private fun splitTerms(value: String): List<String> = normalize(value).split(' ').filter { it.length >= 3 && it !in STOP_WORDS }.distinct()
    private val STOP_WORDS = setOf("the", "and", "with", "vs", "versus", "game", "live", "network", "sports")
    private fun broadcastAliases(value: String): List<String> {
        val n = normalize(value); if (n.isBlank()) return emptyList(); val aliases = linkedSetOf(n)
        when { n.contains("espn plus") || n == "espn+" -> aliases += listOf("espn+", "espn plus", "espn"); n.contains("espn2") -> aliases += listOf("espn2", "espn 2", "espn"); n.contains("espnu") -> aliases += listOf("espnu", "espn u", "espn"); n.contains("fs1") -> aliases += listOf("fs1", "fox sports 1", "fox sports"); n.contains("fs2") -> aliases += listOf("fs2", "fox sports 2", "fox sports"); n.contains("cbs sports") -> aliases += listOf("cbs sports", "cbs"); n.contains("acc network") -> aliases += listOf("acc network", "acc"); n.contains("sec network") -> aliases += listOf("sec network", "sec"); n.contains("big ten") -> aliases += listOf("big ten network", "btn", "big ten"); n.contains("nfl network") -> aliases += listOf("nfl network", "nfl"); n.contains("netflix") -> aliases += listOf("netflix", "wwe"); n.contains("usa network") || n == "usa" -> aliases += listOf("usa network", "usa", "wwe"); n.contains("wwe network") -> aliases += listOf("wwe network", "wwe"); n.contains("peacock") -> aliases += listOf("peacock", "wwe"); n == "cw" || n.contains("cw network") -> aliases += listOf("cw", "cw network", "wwe") }
        return aliases.map(::normalize).distinct()
    }
    private fun normalize(value: String): String = value.lowercase().replace('&', ' ').replace("+", " plus ").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
    private fun cacheKey(config: SourceConfig): String = listOf(config.type, config.server.trim().removeSuffix("/"), config.username, config.m3uUrl, BuildConfig.PAIRING_BASE_URL).joinToString("|")
    private fun eventCacheKey(config: SourceConfig, event: SportsEvent): String = listOf(cacheKey(config), EventIdentity.id(event), event.title, event.home, event.away, event.league, event.broadcast).joinToString("|")
    private fun dedupe(streams: List<ResolvedStream>): List<ResolvedStream> { val seen = HashSet<String>(); return streams.filter { seen.add(it.url) } }
    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
    private fun loadM3u(url: String): List<ResolvedStream> {
        val result = ArrayList<ResolvedStream>(); var name = ""; var group = "LIVE"; var icon = ""
        for (line in http(url).lineSequence()) { val trimmed = line.trim(); when { trimmed.startsWith("#EXTINF", true) -> { name = trimmed.substringAfterLast(',', "Unnamed").trim(); group = attr(trimmed, "group-title").ifBlank { "LIVE" }; icon = attr(trimmed, "tvg-logo") }; trimmed.isNotBlank() && !trimmed.startsWith("#") -> { if (name.isNotBlank()) result += ResolvedStream(name, group, trimmed, icon); name = ""; group = "LIVE"; icon = "" } } }
        return result
    }
    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply { requestMethod = "GET"; connectTimeout = 3500; readTimeout = 8000; instanceFollowRedirects = true; useCaches = true; setRequestProperty("User-Agent", "XSportsX/2.0"); setRequestProperty("Accept", "application/json, text/plain, */*"); setRequestProperty("Accept-Encoding", "gzip"); setRequestProperty("Connection", "keep-alive") }
        return try { val code = c.responseCode; if (code !in 200..299) error("Source returned HTTP $code"); val raw: InputStream = BufferedInputStream(c.inputStream); val input = if (c.contentEncoding?.contains("gzip", true) == true) GZIPInputStream(raw) else raw; input.bufferedReader(Charsets.UTF_8).use { it.readText() } } finally { c.disconnect() }
    }
    private fun attr(line: String, key: String): String { val regex = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE); return regex.find(line)?.groupValues?.getOrNull(1).orEmpty() }
}
