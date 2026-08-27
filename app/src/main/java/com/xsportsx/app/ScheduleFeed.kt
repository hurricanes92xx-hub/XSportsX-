package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/** Lightweight remote schedule cache. The APK stays small; schedule data lives in the repo feed. */
object ScheduleFeed {
    private const val FEED_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/data/schedule_feed.json"
    private const val CACHE_NAME = "xsportsx_schedule_feed.json"
    private const val MAX_AGE_MS = 24L * 60L * 60L * 1000L

    suspend fun load(context: Context): List<Game> = withContext(Dispatchers.IO) {
        val cached = readCache(context)
        val fresh = runCatching { download() }.getOrNull()
        if (fresh != null) {
            runCatching { context.openFileOutput(CACHE_NAME, Context.MODE_PRIVATE).use { it.write(fresh.toByteArray()) } }
            parse(fresh).ifEmpty { cached }
        } else if (cached != null && System.currentTimeMillis() - cached.first < MAX_AGE_MS * 7) {
            parse(cached.second)
        } else {
            emptyList()
        }
    }

    private fun download(): String {
        val connection = URL(FEED_URL).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 2500
            connection.readTimeout = 5000
            connection.requestMethod = "GET"
            connection.setRequestProperty("User-Agent", "XSportsX/2.0 Android")
            connection.setRequestProperty("Accept", "application/json")
            check(connection.responseCode in 200..299)
            return connection.inputStream.bufferedReader().use { it.readText() }
        } finally { connection.disconnect() }
    }

    private fun readCache(context: Context): Pair<Long, String>? = runCatching {
        val file = context.getFileStreamPath(CACHE_NAME)
        if (!file.exists()) return null
        file.lastModified() to context.openFileInput(CACHE_NAME).bufferedReader().use { it.readText() }
    }.getOrNull()

    private fun parse(raw: String): List<Game> = runCatching {
        val root = JSONObject(raw)
        val events = root.optJSONArray("events") ?: JSONArray()
        buildList {
            for (i in 0 until events.length()) {
                val e = events.optJSONObject(i) ?: continue
                val title = e.optString("title").trim()
                val league = e.optString("league").trim()
                if (title.isBlank() || league.isBlank()) continue
                val start = e.optString("start")
                val time = formatTime(start, e.optString("time"))
                add(Game(league, title, time, e.optString("tag").ifBlank { "UPCOMING" }, e.optString("icon").ifBlank { "•" }))
            }
        }
    }.getOrDefault(emptyList())

    private fun formatTime(start: String, fallback: String): String = runCatching {
        val instant = Instant.parse(start)
        val local = java.time.ZonedDateTime.ofInstant(instant, java.time.ZoneId.systemDefault())
        val formatter = java.time.format.DateTimeFormatter.ofPattern("EEE • h:mm a z")
        formatter.format(local)
    }.getOrDefault(fallback)
}
