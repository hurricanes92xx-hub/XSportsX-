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

    /** Treat a non-terminal scheduled event as live from three minutes before kickoff through kickoff. */
    val isLive: Boolean
        get() {
            if (providerLive || terminal) return providerLive
            val start = startMillis()
            val now = System.currentTimeMillis()
            return start > 0L && now >= start - 3L * 60L * 1000L && now < start &&
                (state.isBlank() || state.equals("pre", true) || state.equals("scheduled", true) || status.contains("upcoming", true) || status.contains("scheduled", true))
        }

    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = startMillis()
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L && !isLive
    }

    /** Explicit UPCOMING/SCHEDULED feed rows remain visible on game day even when only a date was supplied. */
    val isUpcoming: Boolean
        get() {
            if (isLive) return false
            val start = startMillis()
            val now = System.currentTimeMillis()
            if (status.contains("upcoming", true) || status.contains("scheduled", true)) {
                return start >= now - 26L * 60L * 60L * 1000L
            }
            if (start <= now) return false
            return state.equals("pre", true) || state.equals("scheduled", true) || state.isBlank()
        }
}
