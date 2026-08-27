package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * Targeted source discovery. It searches only for the requested event/network
 * instead of building a large global stream catalog.
 *
 * Public sources are limited to the app's configured public registry. User
 * supplied M3U/Xtream sources are treated as authorized/private sources and
 * are searched only after the user has connected them.
 */
data class TargetQuery(
    val event: SportsEvent? = null,
    val network: String = "",
    val extraTerms: List<String> = emptyList()
) {
    fun terms(): List<String> = buildList {
        event?.let {
            add(it.title); add(it.home); add(it.away); add(it.league); add(it.broadcast)
        }
        add(network)
        addAll(extraTerms)
    }.map { normalize(it) }.filter { it.length >= 2 }.distinct()

    companion object {
        private fun normalize(value: String): String = value.lowercase()
            .replace("’", "'")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim().replace(Regex("\\s+"), " ")
    }
}

data class AuthorizedSource(
    val id: String,
    val type: Type,
    val endpoint: String,
    val username: String = "",
    val password: String = ""
) {
    enum class Type { M3U, XTREAM }
}

data class TargetedStream(
    val name: String,
    val group: String,
    val url: String,
    val sourceId: String,
    val sourceType: String,
    val userAgent: String = "",
    val referer: String = "",
    val score: Int = 0
)

class TargetedSourceResolver {
    companion object {
        private const val MAX_RESULTS_PER_SOURCE = 12
        private const val MAX_TOTAL_RESULTS = 40
        private const val MAX_PLAYLIST_BYTES = 8_000_000
        private const val TIMEOUT_MS = 7_000
    }

    private val publicResolver = PublicSourceResolver()

    suspend fun search(
        query: TargetQuery,
        authorizedSources: List<AuthorizedSource> = emptyList()
    ): List<TargetedStream> = withContext(Dispatchers.IO) {
        val terms = query.terms()
        if (terms.isEmpty()) return@withContext emptyList()

        val publicResults = runCatching { publicResolver.load(force = true) }
            .getOrDefault(emptyList())
            .mapNotNull { stream ->
                val score = score(stream.name, stream.group, stream.sourceName, terms)
                if (score <= 0) null else TargetedStream(
                    stream.name, stream.group, stream.url, "public:${stream.sourceName}", "PUBLIC", score = score
                )
            }
            .sortedByDescending { it.score }
            .take(MAX_RESULTS_PER_SOURCE)

        val privateResults = coroutineScope {
            authorizedSources.map { source ->
                async(Dispatchers.IO) { searchAuthorizedSource(source, terms) }
            }.awaitAll().flatten()
        }

        (publicResults + privateResults)
            .distinctBy { it.url }
            .sortedWith(compareByDescending<TargetedStream> { it.score }.thenBy { it.sourceType })
            .take(MAX_TOTAL_RESULTS)
    }

    private suspend fun searchAuthorizedSource(
        source: AuthorizedSource,
        terms: List<String>
    ): List<TargetedStream> = when (source.type) {
        AuthorizedSource.Type.M3U -> {
            val body = fetchText(source.endpoint) ?: return emptyList()
            parseM3u(body, source, terms)
        }
        AuthorizedSource.Type.XTREAM -> searchXtream(source, terms)
    }

    private suspend fun searchXtream(
        source: AuthorizedSource,
        terms: List<String>
    ): List<TargetedStream> {
        val base = source.endpoint.trimEnd('/')
        val params = "username=${enc(source.username)}&password=${enc(source.password)}"
        val urls = listOf(
            "$base/player_api.php?$params&action=get_live_streams",
            "$base/player_api.php?$params&action=get_live_categories"
        )
        val liveJson = fetchText(urls.first()) ?: return emptyList()
        val array = runCatching { JSONArray(liveJson) }.getOrNull() ?: return emptyList()
        val result = ArrayList<TargetedStream>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            val name = item.optString("name")
            val category = item.optString("category_name")
            val score = score(name, category, "XTREAM", terms)
            if (score <= 0) continue
            val streamId = item.optString("stream_id")
            if (streamId.isBlank()) continue
            val ext = item.optString("container_extension").ifBlank { "ts" }
            val streamUrl = "$base/live/${enc(source.username)}/${enc(source.password)}/$streamId.$ext"
            result += TargetedStream(name, category, streamUrl, source.id, "XTREAM", score = score)
            if (result.size >= MAX_RESULTS_PER_SOURCE) break
        }
        return result
    }

    private fun parseM3u(
        text: String,
        source: AuthorizedSource,
        terms: List<String>
    ): List<TargetedStream> {
        val result = ArrayList<TargetedStream>()
        var name = ""
        var group = "LIVE"
        var userAgent = ""
        var referer = ""
        for (line in text.lineSequence()) {
            val value = line.trim()
            when {
                value.startsWith("#EXTINF", true) -> {
                    name = value.substringAfterLast(',', "Unnamed").trim()
                    group = attr(value, "group-title").ifBlank { "LIVE" }
                    userAgent = attr(value, "http-user-agent")
                    referer = attr(value, "http-referrer")
                }
                value.startsWith("#EXTVLCOPT:http-user-agent=", true) -> userAgent = value.substringAfter('=')
                value.startsWith("#EXTVLCOPT:http-referrer=", true) -> referer = value.substringAfter('=')
                value.isNotBlank() && !value.startsWith("#") -> {
                    val score = score(name, group, source.id, terms)
                    if (score > 0 && value.startsWith("http", true)) {
                        result += TargetedStream(name, group, value, source.id, "M3U", userAgent, referer, score)
                    }
                    name = ""; group = "LIVE"; userAgent = ""; referer = ""
                    if (result.size >= MAX_RESULTS_PER_SOURCE) break
                }
            }
        }
        return result
    }

    private fun score(name: String, group: String, source: String, terms: List<String>): Int {
        val hay = normalize("$name $group $source")
        if (hay.isBlank()) return 0
        var best = 0
        for (term in terms) {
            if (hay == term) best = maxOf(best, 100)
            else if (hay.contains(term)) best = maxOf(best, 88)
            else {
                val tokens = term.split(' ').filter { it.length >= 2 }
                val hits = tokens.count { hay.contains(it) }
                if (tokens.isNotEmpty() && hits == tokens.size) best = maxOf(best, 80)
                else if (hits > 0) best = maxOf(best, 55)
            }
        }
        return best
    }

    private suspend fun fetchText(target: String): String? = withContext(Dispatchers.IO) {
        runCatching {
            val c = URL(target).openConnection() as HttpURLConnection
            c.requestMethod = "GET"
            c.connectTimeout = TIMEOUT_MS
            c.readTimeout = TIMEOUT_MS
            c.instanceFollowRedirects = true
            c.setRequestProperty("User-Agent", "XSportsX-targeted-source/1.0")
            c.setRequestProperty("Accept", "application/json,application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
            if (c.responseCode !in 200..299) { c.disconnect(); return@runCatching null }
            val input = BufferedInputStream(c.inputStream)
            val out = StringBuilder(); val buffer = ByteArray(8192); var total = 0
            while (true) {
                val n = input.read(buffer); if (n <= 0) break
                total += n
                if (total > MAX_PLAYLIST_BYTES) break
                out.append(String(buffer, 0, n, Charsets.UTF_8))
            }
            input.close(); c.disconnect(); out.toString()
        }.getOrNull()
    }

    private fun attr(line: String, key: String): String = Regex(
        "$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE
    ).find(line)?.groupValues?.getOrNull(1).orEmpty()

    private fun enc(value: String): String = URLEncoder.encode(value, Charsets.UTF_8.name())

    private fun normalize(value: String): String = value.lowercase()
        .replace("’", "'")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim().replace(Regex("\\s+"), " ")
}
