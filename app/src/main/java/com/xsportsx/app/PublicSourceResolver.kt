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

data class PublicResolvedStream(val name: String, val group: String, val url: String, val iconUrl: String = "", val sourceName: String = "Public source", val latencyMs: Int = 0)

class PublicSourceResolver {
    companion object {
        private const val CACHE_TTL_MS = 10 * 60 * 1000L
        private const val MAX_PLAYLIST_BYTES = 12_000_000
        private const val MAX_CANDIDATES = 500
        private const val PER_SOURCE_CANDIDATES = 180
        private const val MAX_HEALTH_CHECKS = 240
        private const val HEALTH_CONCURRENCY = 16
        private const val MAX_TARGETED_BYTES = 12_000_000
        private const val TARGETED_CONCURRENCY = 6

        private val REGISTRY_URLS = listOf(
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/docs/public-sources-registry.json",
            "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/main/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@android-app/docs/public-sources-registry.json",
            "https://cdn.jsdelivr.net/gh/hurricanes92xx-hub/XSportsX-@main/docs/public-sources-registry.json"
        )

        private val registryHosts = setOf("iptv-org.github.io", "raw.githubusercontent.com", "github.com", "cdn.jsdelivr.net", "dearbulut.github.io", "i.mjh.nz")

        private val networkAliases = mapOf(
            "ESPN" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN Deportes", "ESPN News", "ESPN on ABC", "SECN+", "ACCNX"),
            "FOX" to listOf("FOX", "FOX Sports", "Fox Sports 1", "FS1", "Fox Sports 2", "FS2", "FOX Deportes"),
            "CBS" to listOf("CBS", "CBS Sports", "CBS Sports Network", "CBS Sports HQ", "CBS Sports Golazo"),
            "NBC" to listOf("NBC", "NBC Sports", "NBC Sports NOW", "NBCSN", "Peacock", "USA Network"),
            "ABC" to listOf("ABC", "ESPN on ABC"),
            "TNT" to listOf("TNT", "TNT Sports", "truTV"),
            "NBA" to listOf("NBA TV", "NBA"),
            "NFL" to listOf("NFL Network", "NFL Channel", "NFL"),
            "MLB" to listOf("MLB Network", "MLB"),
            "NHL" to listOf("NHL Network", "NHL"),
            "SEC" to listOf("SEC Network", "SECN", "SEC Network+", "SECN+"),
            "ACC" to listOf("ACC Network", "ACCN", "ACCNX", "ACC Digital Network", "ACCDN"),
            "BTN" to listOf("Big Ten Network", "BTN"),
            "CW" to listOf("The CW", "CW Sports"),
            "FANDUEL" to listOf("FanDuel TV", "FanDuel Racing"),
            "DAZN" to listOf("DAZN", "DAZN Combat"),
            "TSN" to listOf("TSN", "TSN1", "TSN2", "TSN3", "TSN4", "TSN5"),
            "SPORTSNET" to listOf("Sportsnet", "Sportsnet One", "Sportsnet Ontario", "Sportsnet Pacific", "Sportsnet West", "Sportsnet East"),
            "GOLF" to listOf("Golf Channel", "NBC Golf"),
            "TENNIS" to listOf("Tennis Channel"),
            "MOTORSPORT" to listOf("NBC Sports", "USA Network", "FOX Sports", "FS1", "FS2", "TNT Sports", "MotorTrend", "MAVTV"),
            "SOCCER" to listOf("TNT Sports", "CBS Sports Golazo", "Telemundo", "Universo", "FOX Deportes", "TUDN", "beIN Sports", "FIFA+", "Apple TV"),
            "COLLEGE" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "FOX", "FS1", "FS2", "CBS", "CBS Sports Network", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "CBS Sports HQ", "ACCDN", "Pac-12 Insider"),
            "VOLLEYBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "CBS Sports Network", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider", "NCAA", "Volleyball World"),
            "BASKETBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "CBS", "CBS Sports Network", "FOX", "FS1", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider")
        )

        private val sportsTerms = Regex("\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|tbs|tru tv|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|secn|acc network|accn|accdn|big ten|btn|pac 12|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|fubo sports|fanduel|sportsgrid|stadium|fifa\\+|real madrid tv|motorsport|f1|formula|racing|ufc|boxing|nascar|sportsnet|tsn|fifa|abc|cbs|nbc|fox|cw network|peacock|paramount|red bull|rugby|volleyball|lacrosse|wrestling|mavtv|dazn|dazn combat|l'equipe|teledeporte|rta sport|rtsh sport|trace sports stars|unbeaten|world of freesports|more than sports|fuel tv|volleyball world|ncaa|pac 12 insider)\\b", RegexOption.IGNORE_CASE)
    }

    private val cache = LruCache<String, Pair<Long, List<PublicResolvedStream>>>(1)

    suspend fun load(force: Boolean = false): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        val hit = cache.get("public")
        if (!force && hit != null && now - hit.first < CACHE_TTL_MS) return@withContext hit.second
        val registry = fetchRegistry()?.let { runCatching { JSONObject(it) }.getOrNull() } ?: return@withContext hit?.second.orEmpty()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val candidates = ArrayList<PublicResolvedStream>(MAX_CANDIDATES)
        for (i in 0 until sources.length()) {
            if (candidates.size >= MAX_CANDIDATES) break
            val s = sources.optJSONObject(i) ?: continue
            if (!s.optBoolean("enabled", false) || !s.optBoolean("public", false)) continue
            val playlist = s.optString("playlist").trim()
            if (!isAllowedRegistryUrl(playlist)) continue
            val body = fetchText(playlist, MAX_PLAYLIST_BYTES, true) ?: continue
            val remain = MAX_CANDIDATES - candidates.size
            candidates += parseM3u(body, s.optString("name").ifBlank { "Public source" }, s.optString("allowlist"), minOf(PER_SOURCE_CANDIDATES, remain))
        }
        val unique = candidates.distinctBy { it.url }.take(MAX_CANDIDATES)
        val checked = coroutineScope {
            unique.take(MAX_HEALTH_CHECKS).chunked(HEALTH_CONCURRENCY).flatMap { batch ->
                batch.map { async(Dispatchers.IO) { health(it) } }.awaitAll().filterNotNull()
            }
        }
        val good = checked.map { it.url }.toSet()
        val result = (checked + unique.filterNot { it.url in good }).distinctBy { it.url }.take(MAX_CANDIDATES)
        cache.put("public", now to result)
        result
    }

    suspend fun searchTargeted(terms: List<String>): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val expanded = expandNetworkTerms(terms).map(::normalize).filter { it.length >= 2 }.distinct()
        if (expanded.isEmpty()) return@withContext emptyList()
        val registry = fetchRegistry()?.let { runCatching { JSONObject(it) }.getOrNull() } ?: return@withContext emptyList()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val configs = mutableListOf<Triple<String, String, String>>()
        for (i in 0 until sources.length()) {
            val s = sources.optJSONObject(i) ?: continue
            if (s.optBoolean("enabled", false) && s.optBoolean("public", false)) {
                val p = s.optString("playlist").trim()
                if (isAllowedRegistryUrl(p)) configs += Triple(p, s.optString("name").ifBlank { "Public source" }, s.optString("allowlist"))
            }
        }
        coroutineScope {
            configs.chunked(TARGETED_CONCURRENCY).flatMap { batch ->
                batch.map { (p, n, a) ->
                    async(Dispatchers.IO) {
                        runCatching {
                            val body = fetchText(p, MAX_TARGETED_BYTES, true) ?: return@runCatching emptyList<PublicResolvedStream>()
                            parseTargetedM3u(body, n, a, expanded)
                        }.getOrDefault(emptyList())
                    }
                }.awaitAll().flatten()
            }
        }.distinctBy { it.url }.sortedByDescending { targetedScore(it.name, it.group, expanded) }
    }

    private fun expandNetworkTerms(terms: List<String>): List<String> {
        val out = terms.toMutableList()
        for (term in terms) {
            val n = normalize(term)
            networkAliases.entries.firstOrNull { entry ->
                normalize(entry.key) == n || entry.value.any { normalize(it) == n }
            }?.let { out += it.value }
        }
        return out
    }

    private fun parseM3u(text: String, source: String, allow: String, max: Int): List<PublicResolvedStream> {
        val result = ArrayList<PublicResolvedStream>()
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
                    if (name.isNotBlank() && isAllowedStream(value) && isSports(name, group) && matchesAllowlist(name, group, allow)) {
                        result += PublicResolvedStream(name, group, value, icon, source)
                    }
                    name = ""
                    group = "LIVE"
                    icon = ""
                }
            }
            if (result.size >= max) break
        }
        return result
    }

    private fun parseTargetedM3u(text: String, source: String, allow: String, terms: List<String>): List<PublicResolvedStream> {
        val result = ArrayList<PublicResolvedStream>()
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
                    val score = targetedScore(name, group, terms)
                    if (name.isNotBlank() && isAllowedStream(value) && matchesAllowlist(name, group, allow) && score > 0) {
                        result += PublicResolvedStream(name, group, value, icon, source, score)
                    }
                    name = ""
                    group = "LIVE"
                    icon = ""
                }
            }
        }
        return result
    }

    private fun matchesAllowlist(name: String, group: String, allow: String): Boolean =
        allow.isBlank() || allow.split('|').any { it.isNotBlank() && (name.contains(it.trim(), true) || group.contains(it.trim(), true)) }

    private fun targetedScore(name: String, group: String, terms: List<String>): Int {
        val haystack = normalize("$name $group")
        var best = 0
        for (term in terms) {
            if (haystack == term) best = maxOf(best, 100)
            else if (haystack.contains(term)) best = maxOf(best, 90)
            else {
                val tokens = term.split(' ').filter { it.length >= 2 }
                val hits = tokens.count { haystack.contains(it) }
                if (tokens.isNotEmpty() && hits == tokens.size) best = maxOf(best, 80)
                else if (hits > 0) best = maxOf(best, 55)
            }
        }
        return best
    }

    private suspend fun health(stream: PublicResolvedStream): PublicResolvedStream? = withContext(Dispatchers.IO) {
        runCatching {
            val started = System.currentTimeMillis()
            val connection = URL(stream.url).openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 3000
            connection.readTimeout = 3500
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX-public-health/1.1")
            val code = connection.responseCode
            if (code !in 200..299) {
                connection.disconnect()
                return@runCatching null
            }
            val input = BufferedInputStream(connection.inputStream)
            val buffer = ByteArray(4096)
            val count = input.read(buffer)
            input.close()
            connection.disconnect()
            if (count <= 0) return@runCatching null
            stream.copy(latencyMs = (System.currentTimeMillis() - started).toInt())
        }.getOrNull()
    }

    private fun isSports(name: String, group: String) = sportsTerms.containsMatchIn("$name $group")

    private fun isAllowedRegistryUrl(value: String) = runCatching {
        val url = URL(value)
        url.protocol.equals("https", true) && registryHosts.any { url.host.equals(it, true) || url.host.endsWith(".$it", true) }
    }.getOrDefault(false)

    private fun isAllowedStream(value: String) = runCatching { URL(value).protocol.equals("https", true) }.getOrDefault(false)

    private suspend fun fetchRegistry(): String? {
        for (target in REGISTRY_URLS) fetchText(target, 256_000, true)?.let { return it }
        return null
    }

    private suspend fun fetchText(target: String, max: Int, registryOnly: Boolean) = withContext(Dispatchers.IO) {
        runCatching {
            if (registryOnly && !isAllowedRegistryUrl(target)) return@runCatching null
            val connection = URL(target).openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 10000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX-public/1.1")
            if (connection.responseCode !in 200..299) {
                connection.disconnect()
                return@runCatching null
            }
            val input = BufferedInputStream(connection.inputStream)
            val output = StringBuilder()
            val buffer = ByteArray(8192)
            var total = 0
            while (true) {
                val count = input.read(buffer)
                if (count <= 0) break
                total += count
                if (total > max) break
                output.append(String(buffer, 0, count, Charsets.UTF_8))
            }
            input.close()
            connection.disconnect()
            output.toString()
        }.getOrNull()
    }

    private fun attr(line: String, key: String) = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE).find(line)?.groupValues?.getOrNull(1).orEmpty()

    private fun normalize(value: String) = value.lowercase().replace("’", "'").replace(Regex("[^a-z0-9+]+"), " ").trim().replace(Regex("\\s+"), " ")
}
