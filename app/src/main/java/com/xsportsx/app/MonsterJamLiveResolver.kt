package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/** Official Monster Jam YouTube live-event bridge. Only promotes an official live result. */
object MonsterJamLiveResolver {
    private const val LIVE_URL = "https://www.youtube.com/@MonsterJam/live"
    private val videoRegex = Regex("""\"videoId\":\"([A-Za-z0-9_-]{11})\"""")
    private val titleRegex = Regex("""<title>(.*?)</title>""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))

    suspend fun loadLive(): List<SportsEvent> = withContext(Dispatchers.IO) {
        runCatching {
            val html = fetch(LIVE_URL)
            val id = videoRegex.find(html)?.groupValues?.getOrNull(1).orEmpty()
            if (id.isBlank()) return@runCatching emptyList<SportsEvent>()
            val title = titleRegex.find(html)?.groupValues?.getOrNull(1)?.trim()
                ?.replace("&amp;", "&")
                ?.replace("\\u0026", "&")
                ?.takeUnless { it.isNullOrBlank() }
                ?: "Monster Jam Live"
            if (!looksLikeMonsterJam(title, html)) return@runCatching emptyList<SportsEvent>()
            val now = Instant.now().toString()
            listOf(SportsEvent(
                "monster-jam-youtube-$id", "Motorsports", "Monster Jam", title, now,
                "LIVE", "in", "Monster Jam", title, "", "", "Monster Jam", "",
                "https://www.monsterjam.com/en-us/live-streaming/", id
            ))
        }.getOrDefault(emptyList())
    }

    private fun looksLikeMonsterJam(title: String, html: String): Boolean {
        val haystack = (title + " " + html.take(250_000)).lowercase()
        return haystack.contains("monster jam") || haystack.contains("monsterjam")
    }

    private fun fetch(target: String): String {
        val c = URL(target).openConnection() as HttpURLConnection
        c.connectTimeout = 2500
        c.readTimeout = 4500
        c.instanceFollowRedirects = true
        c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/136.0 Mobile Safari/537.36")
        return try {
            if (c.responseCode !in 200..299) return ""
            c.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally { c.disconnect() }
    }
}
