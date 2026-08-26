package com.xsportsx.app

import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

/** Lightweight bridge to the server-side public source registry.
 *  The APK receives only healthy, policy-approved streams; playlists never ship in the APK.
 */
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
        private const val CACHE_TTL_MS = 2 * 60 * 1000L
        private val cache = LruCache<String, Pair<Long, List<PublicResolvedStream>>>(1)
    }

    suspend fun load(force: Boolean = false): List<PublicResolvedStream> = withContext(Dispatchers.IO) {
        val base = BuildConfig.PAIRING_BASE_URL.trimEnd('/')
        val now = System.currentTimeMillis()
        val hit = cache.get(base)
        if (!force && hit != null && now - hit.first < CACHE_TTL_MS) return@withContext hit.second

        val connection = (URL("$base/public-sources.json").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5000
            readTimeout = 10000
            instanceFollowRedirects = true
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "XSportsX/2.0")
        }
        try {
            if (connection.responseCode !in 200..299) error("Public source service returned HTTP ${connection.responseCode}")
            val body = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
            val array = JSONArray(body)
            val result = ArrayList<PublicResolvedStream>(array.length())
            for (i in 0 until array.length()) {
                val item = array.optJSONObject(i) ?: continue
                val url = item.optString("url").trim()
                if (url.isBlank() || !url.startsWith("https://", true)) continue
                result += PublicResolvedStream(
                    name = item.optString("name").ifBlank { "Public Sports Stream" },
                    group = item.optString("group").ifBlank { "Sports" },
                    url = url,
                    iconUrl = item.optString("logo"),
                    sourceName = item.optString("sourceName").ifBlank { "Public source" },
                    latencyMs = item.optJSONObject("health")?.optInt("latencyMs", 0) ?: 0
                )
            }
            cache.put(base, now to result)
            result
        } finally {
            connection.disconnect()
        }
    }
}
