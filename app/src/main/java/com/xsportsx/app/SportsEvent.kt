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

    private val providerLive: Boolean
        get() = state.equals("in", true) || state.equals("live", true) || status.contains("live", true) || status.contains("in progress", true)

    private val terminal: Boolean
        get() = status.contains("final", true) || status.contains("finished", true) || status.contains("cancel", true) || status.contains("postpon", true) || state.equals("post", true) || state.equals("final", true)

    /**
     * Canonical live state. Provider state wins, but a non-terminal event whose
     * scheduled start has passed is promoted to LIVE as a feed-lag fallback.
     * This prevents games such as MLB from remaining in UPCOMING simply because
     * the upstream status field has not flipped yet.
     */
    val isLive: Boolean
        get() {
            if (providerLive) return true
            if (terminal) return false
            val start = startMillis()
            if (start <= 0L) return false
            val now = System.currentTimeMillis()
            return now >= start - 3L * 60L * 1000L && now < start + 6L * 60L * 60L * 1000L
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
