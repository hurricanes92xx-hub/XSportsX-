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
     * Promote scheduled/pre-game rows to LIVE from three minutes before kickoff
     * through a generous six-hour safety window. Feeds sometimes lag their LIVE
     * state update, and long games must not disappear after 30 minutes.
     */
    val isLive: Boolean
        get() {
            if (providerLive) return true
            if (terminal) return false
            val start = startMillis()
            val now = System.currentTimeMillis()
            if (start <= 0L) return false
            val scheduled = state.isBlank() || state.equals("pre", true) || state.equals("scheduled", true) || status.contains("upcoming", true) || status.contains("scheduled", true)
            return scheduled && now >= start - 3L * 60L * 1000L && now < start + 6L * 60L * 60L * 1000L
        }

    fun isPregame(nowMillis: Long = System.currentTimeMillis()): Boolean {
        val start = startMillis()
        return start > nowMillis && start <= nowMillis + 30L * 60L * 1000L && !isLive
    }

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
