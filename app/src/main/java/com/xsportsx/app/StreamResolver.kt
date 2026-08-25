package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** Resolves only streams from the source the user explicitly connected. */
data class ResolvedStream(
    val name: String,
    val group: String,
    val url: String,
    val iconUrl: String = ""
)

class StreamResolver(context: Context) {
    private val store = SourceStore(context.applicationContext)

    suspend fun loadLiveStreams(): List<ResolvedStream> = withContext(Dispatchers.IO) {
        val config = store.load()
        if (!config.isConfigured()) return@withContext emptyList()
        if (config.type == "M3U") loadM3u(config.m3uUrl) else loadXtream(config)
    }

    private fun loadXtream(config: SourceConfig): List<ResolvedStream> {
        val base = config.server.trim().removeSuffix("/")
        val query = "username=${enc(config.username)}&password=${enc(config.password)}"
        val json = http("$base/player_api.php?$query&action=get_live_streams")
        val array = JSONArray(json)
        val result = ArrayList<ResolvedStream>(array.length())
        for (i in 0 until array.length()) {
            val o = array.optJSONObject(i) ?: continue
            val id = o.optString("stream_id")
            val name = o.optString("name").trim()
            if (id.isBlank() || name.isBlank()) continue
            val category = o.optString("category_name").ifBlank { "LIVE" }
            val icon = o.optString("stream_icon")
            // Xtream installations commonly expose both HLS and MPEG-TS forms.
            val hls = "$base/live/${enc(config.username)}/${enc(config.password)}/$id.m3u8"
            result += ResolvedStream(name, category, hls, icon)
        }
        return result
    }

    private fun loadM3u(url: String): List<ResolvedStream> {
        val text = http(url)
        val lines = text.lineSequence().map { it.trim() }.toList()
        val result = ArrayList<ResolvedStream>()
        var name = ""
        var group = "LIVE"
        var icon = ""
        for (line in lines) {
            when {
                line.startsWith("#EXTINF", true) -> {
                    name = line.substringAfterLast(',', "Unnamed").trim()
                    group = attr(line, "group-title").ifBlank { "LIVE" }
                    icon = attr(line, "tvg-logo")
                }
                line.isNotBlank() && !line.startsWith("#") -> {
                    if (name.isNotBlank()) result += ResolvedStream(name, group, line, icon)
                    name = ""
                    group = "LIVE"
                    icon = ""
                }
            }
        }
        return result
    }

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10000
            readTimeout = 20000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX/1.0")
            setRequestProperty("Accept", "application/json, text/plain, */*")
        }
        return try {
            val code = c.responseCode
            if (code !in 200..299) error("Source returned HTTP $code")
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            c.disconnect()
        }
    }

    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")

    private fun attr(line: String, key: String): String {
        val regex = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE)
        return regex.find(line)?.groupValues?.getOrNull(1).orEmpty()
    }
}
