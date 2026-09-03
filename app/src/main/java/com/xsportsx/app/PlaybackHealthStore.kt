package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Persistent playback feedback used to improve candidate ordering between sessions. */
class PlaybackHealthStore(context: Context) {
    data class Health(val successes: Int, val failures: Int, val lastSuccessMs: Long, val lastFailureMs: Long, val latencyMs: Long)

    private val prefs = context.applicationContext.getSharedPreferences("xsportsx_playback_health", Context.MODE_PRIVATE)
    private val map = LinkedHashMap<String, Health>()

    init { load() }

    @Synchronized
    fun recordSuccess(eventId: String, stream: ResolvedStream, latencyMs: Long = Long.MAX_VALUE) {
        if (eventId.isBlank()) return
        record(key(eventId, stream), latencyMs, true)
        record(globalKey(stream), latencyMs, true)
    }

    @Synchronized
    fun recordFailure(eventId: String, stream: ResolvedStream) {
        if (eventId.isBlank()) return
        record(key(eventId, stream), Long.MAX_VALUE, false)
        record(globalKey(stream), Long.MAX_VALUE, false)
    }

    @Synchronized
    fun score(eventId: String, stream: ResolvedStream): Double = scoreKey(key(eventId, stream))

    @Synchronized
    fun globalScore(stream: ResolvedStream): Double = scoreKey(globalKey(stream))

    private fun scoreKey(key: String): Double {
        val h = map[key] ?: return 0.0
        val success = h.successes * 4.0
        val failure = h.failures * 8.0
        val recency = if (h.lastSuccessMs > h.lastFailureMs) 3.0 else 0.0
        val latency = if (h.latencyMs != Long.MAX_VALUE) (1000.0 / h.latencyMs.coerceAtLeast(100L)) else 0.0
        return success - failure + recency + latency
    }

    private fun record(key: String, latencyMs: Long, success: Boolean) {
        val old = map[key]
        map[key] = if (success) {
            Health((old?.successes ?: 0) + 1, old?.failures ?: 0, System.currentTimeMillis(), old?.lastFailureMs ?: 0L, minOf(old?.latencyMs ?: Long.MAX_VALUE, latencyMs.coerceAtLeast(0L)))
        } else {
            Health(old?.successes ?: 0, (old?.failures ?: 0) + 1, old?.lastSuccessMs ?: 0L, System.currentTimeMillis(), old?.latencyMs ?: Long.MAX_VALUE)
        }
        trim(); persist()
    }

    private fun key(eventId: String, stream: ResolvedStream): String = "event|$eventId|${stream.url}"
    private fun globalKey(stream: ResolvedStream): String = "global|${stream.url}"
    private fun trim() { while (map.size > 1536) map.remove(map.entries.first().key) }

    private fun persist() {
        val array = JSONArray()
        map.forEach { (key, h) -> array.put(JSONObject().apply {
            put("key", key); put("successes", h.successes); put("failures", h.failures)
            put("lastSuccessMs", h.lastSuccessMs); put("lastFailureMs", h.lastFailureMs); put("latencyMs", h.latencyMs)
        }) }
        prefs.edit().putString("entries", array.toString()).apply()
    }

    private fun load() {
        val raw = prefs.getString("entries", null) ?: return
        runCatching {
            val array = JSONArray(raw)
            for (i in 0 until array.length()) {
                val o = array.optJSONObject(i) ?: continue
                val key = o.optString("key").trim()
                if (key.isBlank()) continue
                map[key] = Health(o.optInt("successes"), o.optInt("failures"), o.optLong("lastSuccessMs"), o.optLong("lastFailureMs"), o.optLong("latencyMs", Long.MAX_VALUE))
            }
            trim()
        }
    }
}
