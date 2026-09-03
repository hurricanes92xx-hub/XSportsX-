package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Persistent event -> ranked stream candidates cache with health-aware ranking. */
class PreResolvedStreamCache(context: Context) {
    data class Candidate(val stream: ResolvedStream, val rank: Int, val latencyMs: Long = Long.MAX_VALUE, val lastSuccessMs: Long = 0L, val failures: Int = 0, val checkedAtMs: Long = 0L)
    data class Entry(val eventId: String, val candidates: List<Candidate>, val savedAtMs: Long)
    companion object {
        private const val PREFS = "xsportsx_pre_resolved_streams"
        private const val KEY = "entries"
        private const val MAX_EVENTS = 96
        private const val MAX_CANDIDATES = 8
        private const val FAILURE_PENALTY = 25
        const val FRESH_TTL_MS = 2 * 60 * 1000L
        const val STALE_TTL_MS = 30 * 60 * 1000L
    }
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val entries = LinkedHashMap<String, Entry>()
    init { load() }

    @Synchronized fun get(eventId: String, allowStale: Boolean = true, nowMs: Long = System.currentTimeMillis()): Entry? {
        val entry = entries[eventId] ?: return null
        val age = nowMs - entry.savedAtMs
        if (age < 0L || age > STALE_TTL_MS) { entries.remove(eventId); persist(); return null }
        if (!allowStale && age >= FRESH_TTL_MS) return null
        return entry.copy(candidates = rank(entry.candidates, nowMs))
    }

    @Synchronized fun put(eventId: String, streams: List<ResolvedStream>, nowMs: Long = System.currentTimeMillis()) {
        if (eventId.isBlank() || streams.isEmpty()) return
        val previous = entries[eventId]?.candidates.orEmpty().associateBy { it.stream.url }
        val candidates = streams.distinctBy { it.url }.take(MAX_CANDIDATES).mapIndexed { index, stream ->
            val old = previous[stream.url]
            Candidate(stream, index, old?.latencyMs ?: Long.MAX_VALUE, old?.lastSuccessMs ?: 0L, old?.failures ?: 0, old?.checkedAtMs ?: nowMs)
        }
        entries.remove(eventId); entries[eventId] = Entry(eventId, candidates, nowMs); trim(); persist()
    }

    @Synchronized fun reportSuccess(eventId: String, streamUrl: String, latencyMs: Long = Long.MAX_VALUE, nowMs: Long = System.currentTimeMillis()) {
        updateCandidate(eventId, streamUrl, nowMs) { it.copy(lastSuccessMs = nowMs, latencyMs = latencyMs.coerceAtLeast(0L), failures = 0, checkedAtMs = nowMs) }
    }

    @Synchronized fun reportFailure(eventId: String, streamUrl: String, nowMs: Long = System.currentTimeMillis()) {
        updateCandidate(eventId, streamUrl, nowMs) { it.copy(failures = (it.failures + 1).coerceAtMost(20), checkedAtMs = nowMs) }
    }

    @Synchronized fun clear() { entries.clear(); prefs.edit().remove(KEY).apply() }
    @Synchronized fun size(): Int = entries.size

    private fun updateCandidate(eventId: String, streamUrl: String, nowMs: Long, transform: (Candidate) -> Candidate) {
        val entry = entries[eventId] ?: return
        entries[eventId] = entry.copy(candidates = rank(entry.candidates.map { if (it.stream.url == streamUrl) transform(it) else it }, nowMs), savedAtMs = nowMs)
        persist()
    }

    private fun rank(candidates: List<Candidate>, nowMs: Long): List<Candidate> = candidates.sortedWith(compareByDescending<Candidate> {
        val age = if (it.lastSuccessMs > 0L) (nowMs - it.lastSuccessMs).coerceAtLeast(0L) else Long.MAX_VALUE
        val successBonus = when { age < 120_000L -> 100; age < 900_000L -> 50; age < 3_600_000L -> 20; else -> 0 }
        val latencyBonus = if (it.latencyMs != Long.MAX_VALUE) (5000 - it.latencyMs.coerceAtMost(5000)).coerceAtLeast(0) / 100 else 0
        successBonus + latencyBonus - (it.failures * FAILURE_PENALTY) - it.rank
    }.thenBy { it.stream.name.lowercase() }).take(MAX_CANDIDATES)

    private fun trim() { while (entries.size > MAX_EVENTS) entries.remove(entries.entries.first().key) }
    private fun persist() {
        val array = JSONArray()
        entries.values.forEach { entry -> array.put(JSONObject().apply {
            put("eventId", entry.eventId); put("savedAtMs", entry.savedAtMs)
            put("candidates", JSONArray().apply { entry.candidates.forEach { c -> put(JSONObject().apply {
                put("name", c.stream.name); put("group", c.stream.group); put("url", c.stream.url); put("iconUrl", c.stream.iconUrl)
                put("rank", c.rank); put("latencyMs", c.latencyMs); put("lastSuccessMs", c.lastSuccessMs); put("failures", c.failures); put("checkedAtMs", c.checkedAtMs)
            }) } })
        }) }
        prefs.edit().putString(KEY, array.toString()).apply()
    }
    private fun load() {
        val raw = prefs.getString(KEY, null) ?: return
        runCatching { val array = JSONArray(raw); for (i in 0 until array.length()) {
            val obj = array.optJSONObject(i) ?: continue; val eventId = obj.optString("eventId").trim(); val savedAt = obj.optLong("savedAtMs", 0L)
            if (eventId.isBlank() || savedAt <= 0L) continue; val list = obj.optJSONArray("candidates") ?: continue
            val candidates = ArrayList<Candidate>(minOf(list.length(), MAX_CANDIDATES)); for (j in 0 until minOf(list.length(), MAX_CANDIDATES)) {
                val item = list.optJSONObject(j) ?: continue; val url = item.optString("url").trim(); if (url.isBlank()) continue
                candidates += Candidate(ResolvedStream(item.optString("name"), item.optString("group"), url, item.optString("iconUrl")), item.optInt("rank", j), item.optLong("latencyMs", Long.MAX_VALUE), item.optLong("lastSuccessMs", 0L), item.optInt("failures", 0), item.optLong("checkedAtMs", savedAt))
            }
            if (candidates.isNotEmpty()) entries[eventId] = Entry(eventId, candidates, savedAt)
        }; trim() }
    }
}
