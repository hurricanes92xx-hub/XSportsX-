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
        private const val MAX_CANDIDATES = 240
        private const val PER_SOURCE_CANDIDATES = 60
        private const val MAX_HEALTH_CHECKS = 96
        private const val HEALTH_CONCURRENCY = 12
        private const val TARGETED_PER_SOURCE = 12
        private const val TARGETED_TOTAL = 48
        private val REGISTRY_URLS = listOf(
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/docs/public-sources-registry.json",
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@android-app/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/docs/public-sources-registry.json",
            "https://hurricanes92xx-hub.github.io/XSportsX-/public-sources-registry.json"
        )
        private val registryHosts = setOf(
            "iptv-org.github.io", "raw.githubusercontent.com", "github.com", "cdn.jsdelivr.net",
            "dearbulut.github.io", "i.mjh.nz"
        )
        private val sportsTerms = Regex(
            "\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|tbs|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|acc network|accdn|big ten|btn|pac 12|pac-12|baseball|basketball|football|hockey|soccer|cbs sports|nbc sports|fubo sports|fanduel|sportsgrid|stadium|fifa\\+|real madrid tv|motorsport|f1|formula|racing|ufc|boxing|nascar|sportsnet|tsn|fifa|abc|cbs|nbc|fox|the cw|cw network|peacock|paramount|red bull|rugby|volleyball|lacrosse|wrestling|mavtv|tvs sports|dazn combat|glory kickboxing|l\\'equipe|teledeporte|rta sport|rtsh sport|san marino rtv sport|trace sports stars|unbeaten|world of freesports|more than sports|fuel tv|w14dk)\\b",
            RegexOption.IGNORE_CASE
        )
    }

    private val cache = LruCache<String, Pair<Long, List<PublicResolvedStream>>>(1)

    /** Existing global catalog path, retained for non-click-path callers. */
    suspend fun load(force: Boolean = false): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val key = "static-public-registry"
        val now = System.currentTimeMillis()
        val hit = cache.get(key)
        if (!force && hit != null && now - hit.first < CACHE_TTL_MS) return@withContext hit.second
        val registryText = fetchRegistry() ?: return@withContext hit?.second.orEmpty()
        val registry = runCatching { JSONObject(registryText) }.getOrNull() ?: return@withContext hit?.second.orEmpty()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val candidates = ArrayList<PublicResolvedStream>(MAX_CANDIDATES)
        for (i in 0 until sources.length()) {
            if (candidates.size >= MAX_CANDIDATES) break
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            val sourceName = source.optString("name").ifBlank { "Public source" }
            val allowlist = source.optString("allowlist").trim()
            if (!isAllowedRegistryUrl(playlist)) continue
            val body = fetchText(playlist, MAX_PLAYLIST_BYTES, registryOnly = true) ?: continue
            val remaining = MAX_CANDIDATES - candidates.size
            candidates += parseM3u(body, sourceName, allowlist, minOf(PER_SOURCE_CANDIDATES, remaining))
        }
        val unique = candidates.distinctBy { it.url }.take(MAX_CANDIDATES)
        if (unique.isEmpty()) { cache.put(key, now to emptyList()); return@withContext emptyList() }
        val checked = coroutineScope {
            unique.take(MAX_HEALTH_CHECKS).chunked(HEALTH_CONCURRENCY).flatMap { batch ->
                batch.map { stream -> async(Dispatchers.IO) { health(stream) } }.awaitAll().filterNotNull()
            }
        }
        val healthyUrls = checked.map { it.url }.toSet()
        val ordered = if (checked.isNotEmpty()) checked + unique.filterNot { it.url in healthyUrls } else unique
        val result = ordered.distinctBy { it.url }.take(MAX_CANDIDATES)
        cache.put(key, now to result)
        result
    }

    /**
     * Click-path public discovery. Every enabled public playlist gets the same
     * small per-source quota, and only entries matching the requested terms are
     * returned. No global public catalog is built.
     */
    suspend fun searchTargeted(terms: List<String>): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val normalized = terms.map(::normalize).filter { it.length >= 2 }.distinct()
        if (normalized.isEmpty()) return@withContext emptyList()
        val registryText = fetchRegistry() ?: return@withContext emptyList()
        val registry = runCatching { JSONObject(registryText) }.getOrNull() ?: return@withContext emptyList()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val perSource = ArrayList<PublicResolvedStream>()
        for (i in 0 until sources.length()) {
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            val sourceName = source.optString("name").ifBlank { "Public source" }
            val allowlist = source.optString("allowlist").trim()
            if (!isAllowedRegistryUrl(playlist)) continue
            val body = fetchText(playlist, MAX_PLAYLIST_BYTES, registryOnly = true) ?: continue
            perSource += parseTargetedM3u(body, sourceName, allowlist, normalized, TARGETED_PER_SOURCE)
        }
        perSource.distinctBy { it.url }.sortedByDescending { targetedScore(it.name, it.group, normalized) }.take(TARGETED_TOTAL)
    }

    private fun parseM3u(text: String, sourceName: String, allowlist: String, maxResults: Int): List<PublicResolvedStream> {
        val result = ArrayList<PublicResolvedStream>(); var name = ""; var group = "LIVE"; var icon = ""
        for (line in text.lineSequence()) {
            val value = line.trim()
            when {
                value.startsWith("#EXTINF", true) -> { name = value.substringAfterLast(',', "Unnamed").trim(); group = attr(value, "group-title").ifBlank { "LIVE" }; icon = attr(value, "tvg-logo") }
                value.isNotBlank() && !value.startsWith("#") -> {
                    if (name.isNotBlank() && isAllowedStream(value) && isSports(name, group) && matchesAllowlist(name, allowlist)) result += PublicResolvedStream(name, group, value, icon, sourceName)
                    name = ""; group = "LIVE"; icon = ""
                }
            }
            if (result.size >= maxResults) break
        }
        return result
    }

    private fun parseTargetedM3u(text: String, sourceName: String, allowlist: String, terms: List<String>, maxResults: Int): List<PublicResolvedStream> {
        val result = ArrayList<PublicResolvedStream>(); var name = ""; var group = "LIVE"; var icon = ""
        for (line in text.lineSequence()) {
            val value = line.trim()
            when {
                value.startsWith("#EXTINF", true) -> { name = value.substringAfterLast(',', "Unnamed").trim(); group = attr(value, "group-title").ifBlank { "LIVE" }; icon = attr(value, "tvg-logo") }
                value.isNotBlank() && !value.startsWith("#") -> {
                    val score = targetedScore(name, group, terms)
                    if (name.isNotBlank() && isAllowedStream(value) && matchesAllowlist(name, allowlist) && score > 0) result += PublicResolvedStream(name, group, value, icon, sourceName, score)
                    name = ""; group = "LIVE"; icon = ""
                }
            }
            if (result.size >= maxResults) break
        }
        return result
    }

    private fun targetedScore(name: String, group: String, terms: List<String>): Int {
        val hay = normalize("$name $group")
        var best = 0
        for (term in terms) {
            if (hay == term) best = maxOf(best, 100)
            else if (hay.contains(term)) best = maxOf(best, 90)
            else {
                val tokens = term.split(' ').filter { it.length >= 2 }
                val hits = tokens.count { hay.contains(it) }
                if (tokens.isNotEmpty() && hits == tokens.size) best = maxOf(best, 80)
                else if (hits > 0) best = maxOf(best, 55)
            }
        }
        return best
    }

    private fun matchesAllowlist(name: String, allowlist: String): Boolean = allowlist.isBlank() || allowlist.split('|').any { it.isNotBlank() && name.contains(it.trim(), true) }

    private suspend fun health(stream: PublicResolvedStream): PublicResolvedStream? = withContext(Dispatchers.IO) {
        runCatching {
            val started = System.currentTimeMillis(); val c = URL(stream.url).openConnection() as HttpURLConnection
            c.requestMethod = "GET"; c.connectTimeout = 3000; c.readTimeout = 3500; c.instanceFollowRedirects = true
            c.setRequestProperty("User-Agent", "XSportsX-public-health/1.0"); c.setRequestProperty("Accept", "application/vnd.apple.mpegurl,application/x-mpegURL,video/*,*/*")
            val code = c.responseCode
            if (code !in 200..299) { c.disconnect(); return@withContext null }
            val type = c.contentType.orEmpty(); val input = BufferedInputStream(c.inputStream); val buffer = ByteArray(4096); val count = input.read(buffer)
            input.close(); c.disconnect(); if (count <= 0) return@withContext null
            val prefix = String(buffer, 0, count, Charsets.UTF_8)
            if (!(type.contains("mpegurl", true) || type.contains("video", true) || type.contains("octet-stream", true) || prefix.contains("#EXTM3U", true))) return@withContext null
            stream.copy(latencyMs = (System.currentTimeMillis() - started).toInt())
        }.getOrNull()
    }

    private fun isSports(name: String, group: String): Boolean = sportsTerms.containsMatchIn("$name $group")
    private fun isAllowedRegistryUrl(target: String): Boolean = runCatching { val uri = URL(target); uri.protocol.equals("https", true) && registryHosts.any { host -> uri.host.equals(host, true) || uri.host.endsWith(".$host", true) } }.getOrDefault(false)
    private fun isAllowedStream(target: String): Boolean = runCatching { URL(target).protocol.equals("https", true) }.getOrDefault(false)
    private suspend fun fetchRegistry(): String? = REGISTRY_URLS.asSequence().mapNotNull { fetchText(it, 256_000, registryOnly = true) }.firstOrNull()
    private fun fetchText(target: String, maxBytes: Int = MAX_PLAYLIST_BYTES, registryOnly: Boolean = false): String? = runCatching {
        if (registryOnly && !isAllowedRegistryUrl(target)) return null
        if (!registryOnly && !isAllowedStream(target)) return null
        val c = URL(target).openConnection() as HttpURLConnection
        c.requestMethod = "GET"; c.connectTimeout = 5000; c.readTimeout = 10000; c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "XSportsX-public-registry/1.0"); c.setRequestProperty("Accept", "application/json,application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
        val code = c.responseCode; if (code !in 200..299) { c.disconnect(); return null }
        val input = BufferedInputStream(c.inputStream); val out = StringBuilder(); val buffer = ByteArray(8192); var total = 0
        while (true) { val n = input.read(buffer); if (n <= 0) break; total += n; if (total > maxBytes) break; out.append(String(buffer, 0, n, Charsets.UTF_8)) }
        input.close(); c.disconnect(); out.toString()
    }.getOrNull()
    private fun attr(line: String, key: String): String = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()
    private fun normalize(value: String): String = value.lowercase().replace("’", "'").replace(Regex("[^a-z0-9]+"), " ").trim().replace(Regex("\\s+"), " ")
}
