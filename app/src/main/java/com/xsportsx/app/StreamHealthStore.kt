package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Persistent source health used to rank known candidates without probing streams blindly. */
class StreamHealthStore(context: Context) {
    data class Health(val successes: Int = 0, val failures: Int = 0, val lastSuccessMs: Long = 0L, val lastFailureMs: Long = 0L, val lastLatencyMs: Long = Long.MAX_VALUE)

    companion object {
        private const val PREFS = "xsportsx_stream_health"
        private const val KEY = "health"
        private const val MAX_ENTRIES = 512
        private const val FAILURE_PENALTY = 20
        private const val SUCCESS_BONUS = 12
    }

    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val entries = LinkedHashMap<String, Health>()

    init { load() }

    @Synchronized
    fun recordSuccess(url: String, latencyMs: Long = Long.MAX_VALUE) {
        if (url.isBlank()) return
        val old = entries[url] ?: Health()
        entries.remove(url)
        entries[url] = old.copy(
            successes = old.successes + 1,
            lastSuccessMs = System.currentTimeMillis(),
            lastLatencyMs = latencyMs.coerceAtLeast(0L)
        )
        trim(); persist()
    }

    @Synchronized
    fun recordFailure(url: String) {
        if (url.isBlank()) return
        val old = entries[url] ?: Health()
        entries.remove(url)
        entries[url] = old.copy(failures = old.failures + 1, lastFailureMs = System.currentTimeMillis())
        trim(); persist()
    }

    @Synchronized
    fun score(url: String, nowMs: Long = System.currentTimeMillis()): Int {
        val h = entries[url] ?: return 0
        val success = h.successes * SUCCESS_BONUS
        val failure = h.failures * FAILURE_PENALTY
        val recentFailurePenalty = if (nowMs - h.lastFailureMs in 0..120_000L) 35 else 0
        val recentSuccessBonus = if (nowMs - h.lastSuccessMs in 0..300_000L) 10 else 0
        val latencyPenalty = if (h.lastLatencyMs == Long.MAX_VALUE) 0 else (h.lastLatencyMs / 250L).toInt().coerceAtMost(20)
        return success - failure - recentFailurePenalty + recentSuccessBonus - latencyPenalty
    }

    @Synchronized
    fun health(url: String): Health = entries[url] ?: Health()

    @Synchronized
    fun clear() { entries.clear(); prefs.edit().remove(KEY).apply() }

    private fun trim() { while (entries.size > MAX_ENTRIES) entries.remove(entries.entries.first().key) }

    private fun persist() {
        val array = JSONArray()
        entries.forEach { (url, h) ->
            array.put(JSONObject().apply {
                put("url", url); put("successes", h.successes); put("failures", h.failures)
                put("lastSuccessMs", h.lastSuccessMs); put("lastFailureMs", h.lastFailureMs); put("lastLatencyMs", h.lastLatencyMs)
            })
        }
        prefs.edit().putString(KEY, array.toString()).apply()
    }

    private fun load() {
        val raw = prefs.getString(KEY, null) ?: return
        runCatching {
            val array = JSONArray(raw)
            for (i in 0 until array.length()) {
                val o = array.optJSONObject(i) ?: continue
                val url = o.optString("url").trim()
                if (url.isBlank()) continue
                entries[url] = Health(
                    o.optInt("successes", 0), o.optInt("failures", 0),
                    o.optLong("lastSuccessMs", 0L), o.optLong("lastFailureMs", 0L),
                    o.optLong("lastLatencyMs", Long.MAX_VALUE)
                )
            }
            trim()
        }
    }
}
