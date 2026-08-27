package com.xsportsx.app

import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL

data class PublicResolvedStream(
    val name: String,
    val group: String,
    val url: String,
    val iconUrl: String = "",
    val sourceName: String = "Public source",
    val latencyMs: Int = 0
)

class PublicSourceResolver {
    companion object {
        private const val CACHE_TTL_MS = 15 * 60 * 1000L
        private const val MAX_PLAYLIST_BYTES = 8_000_000
        private const val MAX_CANDIDATES = 160
        private const val PER_SOURCE_CANDIDATES = 20
        private const val MAX_HEALTH_CHECKS = 48
        private val REGISTRY_URLS = listOf(
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/docs/public-sources-registry.json",
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@android-app/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/docs/public-sources-registry.json",
            "https://hurricanes92xx-hub.github.io/XSportsX-/public-sources-registry.json"
        )
        private val approvedHosts = setOf(
            "iptv-org.github.io", "raw.githubusercontent.com", "github.com", "cdn.jsdelivr.net",
            "dearbulut.github.io", "wurl.com", "amagi.tv", "tubi.video", "splus.ir", "akamaized.net", "cloudfront.net",
            "pluto.tv", "samsungcloud.tv", "plex.tv", "roku.com",
            "tjktv.org", "rtatv.akamaized.net", "jmp2.uk", "i.mjh.nz"
        )
        private val sportsTerms = Regex(
            "\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|tbs|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|acc network|big ten|btn|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|bein|sky sport|f1|formula|racing|ufc|boxing|nascar|pga|sportsnet|tsn|fifa|abc|cbs|nbc|fox|the cw|cw network|peacock|paramount|red bull|rugby|volleyball|motorsport)\\b",
            RegexOption.IGNORE_CASE
        )
    }

    private val cache = LruCache<String, Pair<Long, List<PublicResolvedStream>>>(1)

    suspend fun load(force: Boolean = false): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val key = "static-public-registry"
        val now = System.currentTimeMillis()
        val hit = cache.get(key)
        if (!force && hit != null && now - hit.first < CACHE_TTL_MS) return@withContext hit.second

        val registryText = REGISTRY_URLS.asSequence().mapNotNull { fetchText(it) }.firstOrNull()
            ?: return@withContext hit?.second.orEmpty()
        val registry = runCatching { JSONObject(registryText) }.getOrNull()
            ?: return@withContext hit?.second.orEmpty()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val candidates = ArrayList<PublicResolvedStream>(MAX_CANDIDATES)

        // Every enabled public source gets its own quota. The old implementation
        // let the first large playlist consume all 160 slots, so later sources
        // were technically configured but never reached the app UI.
        for (i in 0 until sources.length()) {
            if (candidates.size >= MAX_CANDIDATES) break
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            val sourceName = source.optString("name").ifBlank { "Public source" }
            if (!isAllowed(playlist)) continue
            val body = fetchText(playlist, MAX_PLAYLIST_BYTES) ?: continue
            val remaining = MAX_CANDIDATES - candidates.size
            candidates += parseM3u(body, sourceName, minOf(PER_SOURCE_CANDIDATES, remaining))
        }

        val unique = candidates.distinctBy { it.url }.take(MAX_CANDIDATES)
        val checked = coroutineScope {
            unique.take(MAX_HEALTH_CHECKS).map { stream -> async { health(stream) } }
                .awaitAll().filterNotNull()
        }
        val result = checked.sortedWith(compareBy<PublicResolvedStream> { it.sourceName }.thenBy { it.latencyMs })
        cache.put(key, now to result)
        result
    }

    private fun parseM3u(text: String, sourceName: String, maxResults: Int): List<PublicResolvedStream> {
        val result = ArrayList<PublicResolvedStream>()
        var name = ""; var group = "LIVE"; var icon = ""
        for (line in text.lineSequence()) {
            val value = line.trim()
            when {
                value.startsWith("#EXTINF", true) -> {
                    name = value.substringAfterLast(',', "Unnamed").trim()
                    group = attr(value, "group-title").ifBlank { "LIVE" }
                    icon = attr(value, "tvg-logo")
                }
                value.isNotBlank() && !value.startsWith("#") -> {
                    if (name.isNotBlank() && isAllowed(value) && isSports(name, group)) {
                        result += PublicResolvedStream(name, group, value, icon, sourceName)
                    }
                    name = ""; group = "LIVE"; icon = ""
                }
            }
            if (result.size >= maxResults) break
        }
        return result
    }

    private suspend fun health(stream: PublicResolvedStream): PublicResolvedStream? = withContext(Dispatchers.IO) {
        runCatching {
            val started = System.currentTimeMillis()
            val c = URL(stream.url).openConnection() as HttpURLConnection
            c.requestMethod = "GET"; c.connectTimeout = 3000; c.readTimeout = 3500
            c.instanceFollowRedirects = true
            c.setRequestProperty("User-Agent", "XSportsX-public-health/1.0")
            c.setRequestProperty("Accept", "application/vnd.apple.mpegurl,application/x-mpegURL,video/*,*/*")
            val code = c.responseCode
            if (code !in 200..299) { c.disconnect(); return@withContext null }
            val type = c.contentType.orEmpty()
            val input = BufferedInputStream(c.inputStream)
            val buffer = ByteArray(4096); val count = input.read(buffer)
            input.close(); c.disconnect()
            if (count <= 0) return@withContext null
            val prefix = String(buffer, 0, count, Charsets.UTF_8)
            if (!(type.contains("mpegurl", true) || type.contains("video", true) || prefix.contains("#EXTM3U", true))) return@withContext null
            stream.copy(latencyMs = (System.currentTimeMillis() - started).toInt())
        }.getOrNull()
    }

    private fun isSports(name: String, group: String): Boolean = sportsTerms.containsMatchIn("$name $group")

    private fun isAllowed(target: String): Boolean = runCatching {
        val uri = URL(target)
        uri.protocol.equals("https", true) && approvedHosts.any { host ->
            uri.host.equals(host, true) || uri.host.endsWith(".$host", true)
        }
    }.getOrDefault(false)

    private fun fetchText(target: String, maxBytes: Int = MAX_PLAYLIST_BYTES): String? = runCatching {
        if (!isAllowed(target)) return null
        val c = URL(target).openConnection() as HttpURLConnection
        c.requestMethod = "GET"; c.connectTimeout = 5000; c.readTimeout = 10000; c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "XSportsX-public-registry/1.0")
        c.setRequestProperty("Accept", "application/json,application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
        val code = c.responseCode
        if (code !in 200..299) { c.disconnect(); return null }
        val input = BufferedInputStream(c.inputStream); val out = StringBuilder(); val buffer = ByteArray(8192); var total = 0
        while (true) { val n = input.read(buffer); if (n <= 0) break; total += n; if (total > maxBytes) break; out.append(String(buffer, 0, n, Charsets.UTF_8)) }
        input.close(); c.disconnect(); out.toString()
    }.getOrNull()

    private fun attr(line: String, key: String): String =
        Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()
}
