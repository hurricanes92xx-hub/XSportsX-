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
    val isLive: Boolean
        get() = state.equals("in", true) || state.equals("live", true) || status.contains("live", true) || status.contains("in progress", true)

    private fun startMillis(): Long = runCatching { java.time.Instant.parse(startUtc).toEpochMilli() }.getOrDefault(0L)

    /** True for scheduled events beginning within the next 30 minutes. */
    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = startMillis()
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L && !isLive
    }

    /** Feed events explicitly tagged UPCOMING remain visible when a provider supplied date-only midnight. */
    val isUpcoming: Boolean
        get() {
            if (isLive) return false
            val start = startMillis()
            val now = System.currentTimeMillis()
            if (status.contains("upcoming", true) || status.contains("scheduled", true)) {
                return start >= now - 18L * 60L * 60L * 1000L
            }
            if (start <= now) return false
            return state.equals("pre", true) ||
                state.equals("scheduled", true) ||
                state.isBlank()
        }
}
