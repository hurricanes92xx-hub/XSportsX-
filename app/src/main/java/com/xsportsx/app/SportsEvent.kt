package com.xsportsx.app

/** Canonical schedule event model shared by schedule UI, matchers and players. */
data class SportsEvent(
    val id: String,
    val sport: String,
    val league: String,
    val title: String,
    val startUtc: String,
    val status: String = "",
    val state: String = "",
    val home: String = "",
    val away: String = "",
    val homeLogo: String = "",
    val awayLogo: String = "",
    val broadcast: String = "",
    val artUrl: String = "",
    val sourceUrl: String = "",
    val youtubeVideoId: String = ""
) {
    private fun startMillis(): Long = runCatching { java.time.Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)
    private val providerLive: Boolean get() = state.equals("in", true) || state.equals("live", true) || status.contains("live", true) || status.contains("in progress", true)
    private val terminal: Boolean get() = status.contains("final", true) || status.contains("finished", true) || status.contains("cancel", true) || status.contains("postpon", true) || state.equals("post", true) || state.equals("final", true)

    /** Sport-aware feed-lag fallback; provider LIVE and explicit terminal states always win. */
    val isLive: Boolean
        get() {
            if (providerLive) return true
            if (terminal) return false
            val start = startMillis()
            if (start <= 0L) return false
            val now = System.currentTimeMillis()
            val key = "$sport $league $title".lowercase()
            val window = when {
                key.contains("mlb") || key.contains("baseball") -> 6L * 60L * 60L * 1000L
                key.contains("soccer") -> 3L * 60L * 60L * 1000L
                key.contains("volleyball") -> 3L * 60L * 60L * 1000L
                key.contains("tennis") -> 5L * 60L * 60L * 1000L
                key.contains("nfl") || key.contains("football") -> 5L * 60L * 60L * 1000L
                key.contains("hockey") -> 4L * 60L * 60L * 1000L
                key.contains("basketball") -> 4L * 60L * 60L * 1000L
                key.contains("golf") -> 7L * 60L * 60L * 1000L
                else -> 4L * 60L * 60L * 1000L
            }
            return now >= start - 3L * 60L * 1000L && now < start + window
        }

    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = startMillis()
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L && !isLive
    }

    val isUpcoming: Boolean
        get() {
            if (isLive || terminal) return false
            val start = startMillis()
            val now = System.currentTimeMillis()
            return start > now && start <= now + 3L * 24L * 60L * 60L * 1000L
        }
}
