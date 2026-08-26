package com.xsportsx.app

import android.content.Context
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

/**
 * Lightweight public-source registry client.
 *
 * The registry is hosted on GitHub, not Render, so public-source discovery
 * remains available even when the XSportsX backend is suspended.
 */
class PublicSourceRegistry(private val context: Context) {
    companion object {
        private const val REGISTRY_PRIMARY = "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/public-sources-registry.json"
        private const val REGISTRY_FALLBACK = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/public-sources-registry.json"
        private const val CACHE_TTL_MS = 15 * 60 * 1000L
        private const val MAX_PLAYLIST_BYTES = 8_000_000
        private const val MAX_STREAMS = 120
        private const val MAX_HEALTH_CHECKS = 24
        private val APPROVED_HOSTS = setOf(
            "iptv-org.github.io",
            "raw.githubusercontent.com",
            "github.com",
            "wurl.com",
            "amagi.tv",
            "tubi.video",
            "splus.ir",
            "akamaized.net",
            "tjktv.org",
            "rtatv.akamaized.net"
        )

        @Volatile private var cached: List<ResolvedStream>? = null
        @Volatile private var cachedAt = 0L
    }

    suspend fun loadHealthyPublicStreams(force: Boolean = false): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        cached?.let { if (!force && now - cachedAt < CACHE_TTL_MS) return@withContext it }

        val registryText = fetchText(REGISTRY_PRIMARY) ?: fetchText(REGISTRY_FALLBACK) ?: return@withContext cached.orEmpty()
        val registry = runCatching { JSONObject(registryText) }.getOrNull() ?: return@withContext cached.orEmpty()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val candidates = ArrayList<ResolvedStream>()

        for (i in 0 until sources.length()) {
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            val sourceName = source.optString("name", "Public Sports")
            if (!isAllowed(playlist)) continue
            val text = fetchText(playlist, MAX_PLAYLIST_BYTES) ?: continue
            candidates += parseM3u(text, sourceName)
            if (candidates.size >= MAX_STREAMS) break
        }

        val unique = candidates.distinctBy { it.url }.take(MAX_STREAMS)
        val healthy = coroutineScope {
            unique.take(MAX_HEALTH_CHECKS).map { stream ->
                async { if (healthy(stream.url)) stream else null }
            }.awaitAll().filterNotNull()
        }
        val result = if (healthy.isNotEmpty()) healthy else unique
        cached = result
        cachedAt = System.currentTimeMillis()
        result
    }

    private fun parseM3u(text: String, sourceName: String): List<ResolvedStream> {
        val result = ArrayList<ResolvedStream>()
        var name = ""
        var group = "LIVE"
        var icon = ""
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
                        result += ResolvedStream("$name • $sourceName", group, value, icon)
                    }
                    name = ""; group = "LIVE"; icon = ""
                }
            }
            if (result.size >= MAX_STREAMS) break
        }
        return result
    }

    private fun isSports(name: String, group: String): Boolean =
        Regex("\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|acc network|big ten|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|bein|sky sport|f1|formula|racing|ufc|boxing|nascar|pga|sportsnet|tsn|fifa)\\b", RegexOption.IGNORE_CASE)
            .containsMatchIn("$name $group")

    private fun isAllowed(target: String): Boolean = runCatching {
        val uri = URL(target)
        uri.protocol.equals("https", true) && APPROVED_HOSTS.any { host ->
            uri.host.equals(host, true) || uri.host.endsWith(".$host", true)
        }
    }.getOrDefault(false)

    private fun healthy(target: String): Boolean = runCatching {
        val c = URL(target).openConnection() as HttpURLConnection
        c.requestMethod = "GET"
        c.connectTimeout = 3000
        c.readTimeout = 3500
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "XSportsX-public-health/1.0")
        c.setRequestProperty("Accept", "application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
        val code = c.responseCode
        if (code !in 200..299) { c.disconnect(); return false }
        val contentType = c.contentType.orEmpty()
        val input = BufferedInputStream(c.inputStream)
        val buffer = ByteArray(4096)
        val count = input.read(buffer)
        input.close(); c.disconnect()
        count > 0 && (contentType.contains("mpegurl", true) || String(buffer, 0, count).contains("#EXTM3U", true) || contentType.contains("video", true))
    }.getOrDefault(false)

    private fun fetchText(target: String, maxBytes: Int = MAX_PLAYLIST_BYTES): String? = runCatching {
        if (!isAllowed(target)) return null
        val c = URL(target).openConnection() as HttpURLConnection
        c.requestMethod = "GET"
        c.connectTimeout = 5000
        c.readTimeout = 10000
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "XSportsX-public-registry/1.0")
        val input = BufferedInputStream(c.inputStream)
        val out = StringBuilder()
        val buffer = ByteArray(8192)
        var total = 0
        while (true) {
            val n = input.read(buffer)
            if (n <= 0) break
            total += n
            if (total > maxBytes) break
            out.append(String(buffer, 0, n, Charsets.UTF_8))
        }
        input.close(); c.disconnect()
        out.toString()
    }.getOrNull()

    private fun attr(line: String, key: String): String =
        Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()
}
