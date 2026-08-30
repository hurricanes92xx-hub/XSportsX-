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

        private val registryHosts = setOf(
            "iptv-org.github.io", "raw.githubusercontent.com", "github.com",
            "cdn.jsdelivr.net", "dearbulut.github.io", "i.mjh.nz"
        )

        /* Broadcast map is deliberately used as a search guide. It never creates a
           stream and never authorizes a source; it only expands a requested sport,
           league, or network into relevant channel aliases. */
        private val broadcastMap = linkedMapOf(
            "NFL" to listOf("NFL Network", "NFL Channel", "ESPN", "ABC", "FOX", "FS1", "FS2", "CBS", "NBC", "USA Network", "Peacock", "Prime Video", "Tubi"),
            "NBA" to listOf("NBA TV", "ESPN", "ABC", "NBC", "Peacock", "Prime Video"),
            "WNBA" to listOf("ESPN", "ESPN2", "ABC", "ESPN+", "NBA TV", "CBS Sports Network", "ION"),
            "MLB" to listOf("MLB Network", "FOX", "FS1", "ESPN", "TBS", "ABC", "NBC", "Peacock", "FOX Deportes", "Apple TV"),
            "NHL" to listOf("NHL Network", "ESPN", "ABC", "TNT", "TNT Sports", "truTV", "Sportsnet", "TSN"),
            "NCAA FOOTBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "FOX", "FS1", "FS2", "CBS", "CBS Sports Network", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "Pac-12 Insider"),
            "NCAA BASKETBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "CBS", "CBS Sports Network", "FOX", "FS1", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "Pac-12 Insider"),
            "NCAA VOLLEYBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "CBS Sports Network", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider", "NCAA", "Volleyball World"),
            "NCAA BASEBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "CBS Sports Network", "FOX", "FS1", "MLB Network"),
            "NCAA SOFTBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "NCAA"),
            "SOCCER" to listOf("ESPN", "ESPN+", "ABC", "FOX", "FS1", "FOX Deportes", "CBS Sports Golazo", "TNT Sports", "Telemundo", "Universo", "TUDN", "beIN Sports", "FIFA+", "Apple TV", "Peacock"),
            "GOLF" to listOf("Golf Channel", "NBC", "Peacock", "CBS", "CBS Sports", "ESPN", "ESPN+", "USA Network"),
            "TENNIS" to listOf("Tennis Channel", "ESPN", "ESPN+", "ABC", "CBS", "Peacock", "T2"),
            "MOTORSPORT" to listOf("FOX Sports", "FS1", "FS2", "NBC Sports", "NBC", "USA Network", "Peacock", "TNT Sports", "Prime Video", "MotorTrend", "MAVTV", "F1 TV"),
            "NASCAR" to listOf("FOX", "FS1", "NBC", "USA Network", "Peacock", "Prime Video", "TNT Sports"),
            "F1" to listOf("ESPN", "ABC", "ESPN2", "ESPN+", "F1 TV", "Sky Sports F1"),
            "UFC" to listOf("ESPN", "ESPN+", "ABC", "TNT Sports", "TBS"),
            "BOXING" to listOf("ESPN", "ESPN+", "DAZN", "FOX Sports", "FS1", "CBS Sports", "TNT Sports", "Prime Video"),
            "PBR" to listOf("CBS Sports Network", "CBS", "FOX Sports", "FS1", "TUDN", "PBR"),
            "MONSTER JAM" to listOf("Monster Jam", "YouTube", "NBC Sports", "Peacock"),
            "COLLEGE" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "FOX", "FS1", "FS2", "CBS", "CBS Sports Network", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider"),
            "VOLLEYBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "CBS Sports Network", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider", "NCAA", "Volleyball World"),
            "BASKETBALL" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN+", "ABC", "CBS", "CBS Sports Network", "FOX", "FS1", "NBC", "Peacock", "SEC Network", "SECN+", "ACC Network", "ACCNX", "Big Ten Network", "BTN", "The CW", "CW Sports", "ACCDN", "Pac-12 Insider")
        )

        private val networkAliases = linkedMapOf(
            "ESPN" to listOf("ESPN", "ESPN2", "ESPNU", "ESPN Deportes", "ESPN News", "ESPN on ABC", "ESPN+"),
            "FOX" to listOf("FOX", "FOX Sports", "Fox Sports 1", "FS1", "Fox Sports 2", "FS2", "FOX Deportes"),
            "CBS" to listOf("CBS", "CBS Sports", "CBS Sports Network", "CBS Sports HQ", "CBS Sports Golazo"),
            "NBC" to listOf("NBC", "NBC Sports", "NBC Sports NOW", "Peacock", "USA Network"),
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
            "MONSTER JAM" to listOf("Monster Jam", "YouTube")
        )

        private val sportsTerms = Regex(
            "\\b(sport|sports|espn|fox sports|fs1|fs2|tnt|tbs|tru tv|nba|mlb|nhl|nfl|ncaaf|ncaab|wnba|sec network|secn|acc network|accn|accdn|big ten|btn|pac 12|baseball|basketball|football|hockey|soccer|tennis|golf|cbs sports|nbc sports|fubo sports|fanduel|sportsgrid|stadium|fifa\\+|motorsport|f1|formula|racing|ufc|boxing|nascar|sportsnet|tsn|fifa|abc|cbs|nbc|fox|cw network|peacock|paramount|red bull|rugby|volleyball|lacrosse|wrestling|mavtv|dazn|dazn combat|ncaa|pac 12 insider|monster jam|volleyball world)\\b",
            RegexOption.IGNORE_CASE
        )
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
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            if (!isAllowedRegistryUrl(playlist)) continue
            val body = fetchText(playlist, MAX_PLAYLIST_BYTES, true) ?: continue
            val remain = MAX_CANDIDATES - candidates.size
            candidates += parseM3u(body, source.optString("name").ifBlank { "Public source" }, source.optString("allowlist"), minOf(PER_SOURCE_CANDIDATES, remain))
        }
        val unique = candidates.distinctBy { it.url }.take(MAX_CANDIDATES)
        val checked = coroutineScope {
            unique.take(MAX_HEALTH_CHECKS).chunked(HEALTH_CONCURRENCY).flatMap { batch ->
                batch.map { async(Dispatchers.IO) { health(it) } }.awaitAll().filterNotNull()
            }
        }
        val good = checked.map { it.url }.toSet()
        val result = (checked + unique.filterNot { it.url in good })
            .distinctBy { it.url }
            .sortedWith(compareByDescending<PublicResolvedStream> { generalSportsScore(it.name, it.group) }.thenBy { it.latencyMs })
            .take(MAX_CANDIDATES)
        cache.put("public", now to result)
        result
    }

    suspend fun searchTargeted(terms: List<String>): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val expanded = expandSearchTerms(terms).map(::normalize).filter { it.length >= 2 }.distinct()
        if (expanded.isEmpty()) return@withContext emptyList()
        val registry = fetchRegistry()?.let { runCatching { JSONObject(it) }.getOrNull() } ?: return@withContext emptyList()
        val sources = registry.optJSONArray("sources") ?: JSONArray()
        val configs = mutableListOf<Triple<String, String, String>>()
        for (i in 0 until sources.length()) {
            val source = sources.optJSONObject(i) ?: continue
            if (!source.optBoolean("enabled", false) || !source.optBoolean("public", false)) continue
            val playlist = source.optString("playlist").trim()
            if (isAllowedRegistryUrl(playlist)) configs += Triple(playlist, source.optString("name").ifBlank { "Public source" }, source.optString("allowlist"))
        }
        coroutineScope {
            configs.chunked(TARGETED_CONCURRENCY).flatMap { batch ->
                batch.map { (playlist, sourceName, allowlist) ->
                    async(Dispatchers.IO) {
                        runCatching {
                            val body = fetchText(playlist, MAX_TARGETED_BYTES, true) ?: return@runCatching emptyList<PublicResolvedStream>()
                            parseTargetedM3u(body, sourceName, allowlist, expanded)
                        }.getOrDefault(emptyList())
                    }
                }.awaitAll().flatten()
            }
        }
            .distinctBy { it.url }
            .sortedWith(compareByDescending<PublicResolvedStream> { targetedScore(it.name, it.group, expanded) }.thenBy { it.latencyMs })
            .take(MAX_CANDIDATES)
    }

    private fun expandSearchTerms(terms: List<String>): List<String> {
        val out = terms.toMutableList()
        val normalizedInput = terms.map(::normalize)
        for ((key, aliases) in broadcastMap) {
            val keyNorm = normalize(key)
            if (normalizedInput.any { it == keyNorm || it.contains(keyNorm) || keyNorm.contains(it) }) out += aliases
        }
        for (term in terms) {
            val normalized = normalize(term)
            networkAliases.entries.firstOrNull { entry ->
                normalize(entry.key) == normalized || entry.value.any { normalize(it) == normalized }
            }?.let { out += it.value }
        }
        return out.distinct()
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
                        result += PublicResolvedStream(name, group, value, icon, source)
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
        allow.isBlank() || allow.split('|').any { token -> token.isNotBlank() && (name.contains(token.trim(), true) || group.contains(token.trim(), true)) }

    private fun targetedScore(name: String, group: String, terms: List<String>): Int {
        val haystack = normalize("$name $group")
        var best = 0
        for (term in terms) {
            val normalized = normalize(term)
            if (haystack == normalized) best = maxOf(best, 120)
            else if (haystack.contains(normalized)) best = maxOf(best, 100)
            else {
                val tokens = normalized.split(' ').filter { it.length >= 2 }
                val hits = tokens.count { haystack.contains(it) }
                if (tokens.isNotEmpty() && hits == tokens.size) best = maxOf(best, 85)
                else if (hits > 0) best = maxOf(best, 35 + hits * 10)
            }
        }
        return best
    }

    private fun generalSportsScore(name: String, group: String): Int {
        val text = "$name $group"
        var score = 0
        if (isSports(name, group)) score += 10
        if (networkAliases.keys.any { text.contains(it, true) }) score += 5
        return score
    }

    private suspend fun health(stream: PublicResolvedStream): PublicResolvedStream? = withContext(Dispatchers.IO) {
        runCatching {
            val started = System.currentTimeMillis()
            val connection = URL(stream.url).openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 3000
            connection.readTimeout = 3500
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX-public-health/1.2")
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
        url.protocol.equals("https", true) && registryHosts.any { host -> url.host.equals(host, true) || url.host.endsWith(".$host", true) }
    }.getOrDefault(false)

    private fun isAllowedStream(value: String) = runCatching { URL(value).protocol.equals("https", true) }.getOrDefault(false)

    private suspend fun fetchRegistry(): String? {
        for (target in REGISTRY_URLS) {
            fetchText(target, 256_000, true)?.let { return it }
        }
        return null
    }

    private suspend fun fetchText(target: String, max: Int, registryOnly: Boolean): String? = withContext(Dispatchers.IO) {
        runCatching {
            if (registryOnly && !isAllowedRegistryUrl(target)) return@runCatching null
            val connection = URL(target).openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 10000
            connection.instanceFollowRedirects = true
            connection.setRequestProperty("User-Agent", "XSportsX-public/1.2")
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

    private fun attr(line: String, key: String): String {
        val regex = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE)
        return regex.find(line)?.groupValues?.getOrNull(1).orEmpty()
    }

    private fun normalize(value: String): String = value
        .lowercase()
        .replace('&', ' ')
        .replace('+', ' ')
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")
}