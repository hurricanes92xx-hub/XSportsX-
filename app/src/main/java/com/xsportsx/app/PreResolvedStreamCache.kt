package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Persistent event -> ranked stream candidates cache.
 * Keeps successful resolution work across screens/process restarts while allowing
 * a short fresh TTL and a longer stale-while-revalidate window.
 */
class PreResolvedStreamCache(context: Context) {
    data class Candidate(
        val stream: ResolvedStream,
        val rank: Int,
        val latencyMs: Long = Long.MAX_VALUE,
        val lastSuccessMs: Long = 0L,
        val failures: Int = 0,
        val checkedAtMs: Long = 0L
    )

    data class Entry(
        val eventId: String,
        val candidates: List<Candidate>,
        val savedAtMs: Long
    )

    companion object {
        private const val PREFS = "xsportsx_pre_resolved_streams"
        private const val KEY = "entries"
        private const val MAX_EVENTS = 96
        private const val MAX_CANDIDATES = 8
        const val FRESH_TTL_MS = 2 * 60 * 1000L
        const val STALE_TTL_MS = 30 * 60 * 1000L
    }

    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val entries = LinkedHashMap<String, Entry>()

    init { load() }

    @Synchronized
    fun get(eventId: String, allowStale: Boolean = true, nowMs: Long = System.currentTimeMillis()): Entry? {
        val entry = entries[eventId] ?: return null
        val age = nowMs - entry.savedAtMs
        if (age < 0L || age > STALE_TTL_MS) {
            entries.remove(eventId)
            persist()
            return null
        }
        if (!allowStale && age >= FRESH_TTL_MS) return null
        return entry
    }

    @Synchronized
    fun put(eventId: String, streams: List<ResolvedStream>, nowMs: Long = System.currentTimeMillis()) {
        if (eventId.isBlank() || streams.isEmpty()) return
        val candidates = streams.distinctBy { it.url }.take(MAX_CANDIDATES).mapIndexed { index, stream ->
            Candidate(stream = stream, rank = index, checkedAtMs = nowMs)
        }
        entries.remove(eventId)
        entries[eventId] = Entry(eventId, candidates, nowMs)
        trim()
        persist()
    }

    @Synchronized
    fun putCandidates(eventId: String, candidates: List<Candidate>, nowMs: Long = System.currentTimeMillis()) {
        if (eventId.isBlank() || candidates.isEmpty()) return
        val ranked = candidates
            .distinctBy { it.stream.url }
            .sortedWith(compareBy<Candidate> { it.rank }.thenBy { it.stream.name.lowercase() })
            .take(MAX_CANDIDATES)
            .mapIndexed { index, it -> it.copy(rank = index, checkedAtMs = nowMs) }
        entries.remove(eventId)
        entries[eventId] = Entry(eventId, ranked, nowMs)
        trim()
        persist()
    }

    @Synchronized
    fun remove(eventId: String) {
        if (entries.remove(eventId) != null) persist()
    }

    @Synchronized
    fun clear() {
        entries.clear()
        prefs.edit().remove(KEY).apply()
    }

    @Synchronized
    fun size(): Int = entries.size

    private fun trim() {
        while (entries.size > MAX_EVENTS) entries.remove(entries.entries.first().key)
    }

    private fun persist() {
        val array = JSONArray()
        entries.values.forEach { entry ->
            val obj = JSONObject().apply {
                put("eventId", entry.eventId)
                put("savedAtMs", entry.savedAtMs)
                val candidates = JSONArray()
                entry.candidates.forEach { candidate ->
                    candidates.put(JSONObject().apply {
                        put("name", candidate.stream.name)
                        put("group", candidate.stream.group)
                        put("url", candidate.stream.url)
                        put("iconUrl", candidate.stream.iconUrl)
                        put("rank", candidate.rank)
                        put("latencyMs", candidate.latencyMs)
                        put("lastSuccessMs", candidate.lastSuccessMs)
                        put("failures", candidate.failures)
                        put("checkedAtMs", candidate.checkedAtMs)
                    })
                }
                put("candidates", candidates)
            }
            array.put(obj)
        }
        prefs.edit().putString(KEY, array.toString()).apply()
    }

    private fun load() {
        val raw = prefs.getString(KEY, null) ?: return
        runCatching {
            val array = JSONArray(raw)
            for (i in 0 until array.length()) {
                val obj = array.optJSONObject(i) ?: continue
                val eventId = obj.optString("eventId").trim()
                val savedAt = obj.optLong("savedAtMs", 0L)
                if (eventId.isBlank() || savedAt <= 0L) continue
                val candidatesJson = obj.optJSONArray("candidates") ?: continue
                val candidates = ArrayList<Candidate>(minOf(candidatesJson.length(), MAX_CANDIDATES))
                for (j in 0 until minOf(candidatesJson.length(), MAX_CANDIDATES)) {
                    val item = candidatesJson.optJSONObject(j) ?: continue
                    val url = item.optString("url").trim()
                    if (url.isBlank()) continue
                    candidates += Candidate(
                        stream = ResolvedStream(
                            item.optString("name"),
                            item.optString("group"),
                            url,
                            item.optString("iconUrl")
                        ),
                        rank = item.optInt("rank", j),
                        latencyMs = item.optLong("latencyMs", Long.MAX_VALUE),
                        lastSuccessMs = item.optLong("lastSuccessMs", 0L),
                        failures = item.optInt("failures", 0),
                        checkedAtMs = item.optLong("checkedAtMs", savedAt)
                    )
                }
                if (candidates.isNotEmpty()) entries[eventId] = Entry(eventId, candidates, savedAt)
            }
            trim()
        }
    }
}
