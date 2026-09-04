package com.xsportsx.app

import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

/** Event/network search context. Broadcast is a ranking signal, never an exclusion filter. */
data class TargetQuery(val event: SportsEvent? = null, val network: String = "", val extraTerms: List<String> = emptyList()) {
    fun terms(): List<String> = buildList {
        event?.let { add(it.title); add(it.home); add(it.away); add(it.league); add(it.broadcast) }
        add(network); addAll(extraTerms)
    }.map(::normalize).filter { it.length >= 2 }.distinct()
    companion object { private fun normalize(value: String): String = value.lowercase().replace("’", "'").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ") }
}

data class AuthorizedSource(val id: String, val type: Type, val endpoint: String, val username: String = "", val password: String = "") { enum class Type { M3U, XTREAM } }
data class TargetedStream(val name: String, val group: String, val url: String, val sourceId: String, val sourceType: String, val userAgent: String = "", val referer: String = "", val score: Int = 0)

class TargetedSourceResolver {
    companion object {
        private const val MAX_PLAYLIST_BYTES = 12_000_000
        private const val REQUEST_TIMEOUT_MS = 7_000L
        private const val CACHE_TTL_MS = 10 * 60 * 1000L
        private val HTTP = OkHttpClient.Builder()
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(5, TimeUnit.SECONDS)
            .writeTimeout(5, TimeUnit.SECONDS)
            .callTimeout(REQUEST_TIMEOUT_MS, TimeUnit.MILLISECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }
    private data class CachedPublic(val at: Long, val results: List<TargetedStream>)
    private val publicResolver = PublicSourceResolver()
    private val queryCache = LruCache<String, CachedPublic>(24)

    /** Fast event-first search. Authorized and public sources are independent. */
    suspend fun search(query: TargetQuery, authorizedSources: List<AuthorizedSource> = emptyList()): List<TargetedStream> = withContext(Dispatchers.IO) {
        val terms = query.terms(); if (terms.isEmpty()) return@withContext emptyList()
        val cacheKey = (terms + authorizedSources.map { "${it.id}:${it.type}:${it.endpoint}" }).joinToString("|")
        val now = System.currentTimeMillis()
        queryCache.get(cacheKey)?.let { if (now - it.at < CACHE_TTL_MS) return@withContext it.results }
        val publicDeferred = async(Dispatchers.IO) { runCatching { publicResolver.searchTargeted(terms) }.getOrDefault(emptyList()).map { s -> TargetedStream(s.name, s.group, s.url, "public:${s.sourceName}", "PUBLIC", score = targetedScore(s.name, s.group, terms) + publicLatencyBonus(s.latencyMs)) } }
        val privateDeferred = async(Dispatchers.IO) { authorizedSources.map { source -> async(Dispatchers.IO) { runCatching { searchAuthorizedSource(source, terms) }.getOrDefault(emptyList()) } }.awaitAll().flatten() }
        val results = (publicDeferred.await() + privateDeferred.await()).filter { it.url.startsWith("http", true) }.distinctBy { normalizeUrl(it.url) }.sortedWith(compareByDescending<TargetedStream> { it.score }.thenBy { it.sourceType })
        queryCache.put(cacheKey, CachedPublic(now, results)); results
    }

    private suspend fun searchAuthorizedSource(source: AuthorizedSource, terms: List<String>): List<TargetedStream> = when (source.type) {
        AuthorizedSource.Type.M3U -> { val body = fetchText(source.endpoint) ?: return emptyList(); parseM3u(body, source, terms) }
        AuthorizedSource.Type.XTREAM -> searchXtream(source, terms)
    }

    private suspend fun searchXtream(source: AuthorizedSource, terms: List<String>): List<TargetedStream> {
        val base = source.endpoint.trimEnd('/'); val params = "username=${enc(source.username)}&password=${enc(source.password)}"
        val liveJson = fetchText("$base/player_api.php?$params&action=get_live_streams") ?: return emptyList()
        val array = runCatching { JSONArray(liveJson) }.getOrNull() ?: return emptyList(); val result = ArrayList<TargetedStream>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue; val name = item.optString("name"); val category = item.optString("category_name"); val score = targetedScore(name, category, terms); if (score <= 0) continue
            val streamId = item.optString("stream_id"); if (streamId.isBlank()) continue; val ext = item.optString("container_extension").ifBlank { "ts" }
            result += TargetedStream(name, category, "$base/live/${enc(source.username)}/${enc(source.password)}/$streamId.$ext", source.id, "XTREAM", score = score + 12)
        }
        return result
    }

    private fun parseM3u(text: String, source: AuthorizedSource, terms: List<String>): List<TargetedStream> {
        val result = ArrayList<TargetedStream>(); var name = ""; var group = "LIVE"; var userAgent = ""; var referer = ""; var pendingExtVlcUserAgent = ""; var pendingExtVlcReferer = ""
        for (line in text.lineSequence()) {
            val value = line.trim()
            when {
                value.startsWith("#EXTINF", true) -> { name = value.substringAfterLast(',', "Unnamed").trim(); group = attr(value, "group-title").ifBlank { "LIVE" }; userAgent = attr(value, "http-user-agent"); referer = attr(value, "http-referrer"); pendingExtVlcUserAgent = ""; pendingExtVlcReferer = "" }
                value.startsWith("#EXTVLCOPT:http-user-agent=", true) -> pendingExtVlcUserAgent = value.substringAfter('=')
                value.startsWith("#EXTVLCOPT:http-referrer=", true) -> pendingExtVlcReferer = value.substringAfter('=')
                value.startsWith("#KODIPROP:inputstream.adaptive.stream_headers=", true) -> { val headers = value.substringAfter('=').trim(); if (headers.contains("User-Agent", true)) userAgent = headers.substringAfter("User-Agent=", "").substringBefore('&').ifBlank { userAgent }; if (headers.contains("Referer", true)) referer = headers.substringAfter("Referer=", "").substringBefore('&').ifBlank { referer } }
                value.isNotBlank() && !value.startsWith("#") -> { val finalUa = pendingExtVlcUserAgent.ifBlank { userAgent }; val finalRef = pendingExtVlcReferer.ifBlank { referer }; val score = targetedScore(name, group, terms); if (name.isNotBlank() && value.startsWith("http", true) && score > 0) result += TargetedStream(name, group, value, source.id, "M3U", finalUa, finalRef, score); name = ""; group = "LIVE"; userAgent = ""; referer = ""; pendingExtVlcUserAgent = ""; pendingExtVlcReferer = "" }
            }
        }
        return result
    }

    private fun targetedScore(name: String, group: String, terms: List<String>): Int {
        val hay = normalize("$name $group"); if (hay.isBlank()) return 0; var best = 0
        for (term in terms) { val tokens = term.split(' ').filter { it.length >= 2 }; when { hay == term -> best = maxOf(best, 100); hay.contains(term) -> best = maxOf(best, 90); tokens.size >= 2 && tokens.all { hay.contains(it) } -> best = maxOf(best, 86); tokens.size >= 2 && tokens.count { hay.contains(it) } >= 2 -> best = maxOf(best, 72); tokens.size == 1 && hay.contains(tokens[0]) -> best = maxOf(best, 65) } }
        return best
    }
    private fun publicLatencyBonus(latencyMs: Int): Int = when { latencyMs in 1..800 -> 8; latencyMs in 801..1800 -> 4; else -> 0 }

    private suspend fun fetchText(target: String): String? = withContext(Dispatchers.IO) {
        runCatching {
            val request = Request.Builder().url(target).get()
                .header("User-Agent", "XSportsX-targeted-source/2.0")
                .header("Accept", "application/json,application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
                .build()
            HTTP.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@runCatching null
                val body = response.body ?: return@runCatching null
                val input = body.byteStream(); val out = StringBuilder(); val buffer = ByteArray(16 * 1024); var total = 0
                while (true) { val n = input.read(buffer); if (n <= 0) break; total += n; if (total > MAX_PLAYLIST_BYTES) break; out.append(String(buffer, 0, n, Charsets.UTF_8)) }
                out.toString()
            }
        }.getOrNull()
    }

    private fun attr(line: String, key: String): String = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()
    private fun enc(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())
    private fun normalize(value: String): String = value.lowercase().replace("’", "'").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
    private fun normalizeUrl(value: String): String = value.trim().trimEnd('/').lowercase()
}
