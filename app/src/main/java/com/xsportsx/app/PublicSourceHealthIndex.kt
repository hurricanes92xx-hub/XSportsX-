package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/** Lightweight local index. Discovery/health work happens off the event click path. */
data class PublicSourceHealth(
    val url: String,
    val channel: String,
    val network: String,
    val sport: String,
    val league: String,
    val eventId: String,
    val availability: Double,
    val latencyMs: Int,
    val recentSuccess: Double,
    val eventMatch: Double,
    val checkedAt: Long
) {
    val score: Double
        get() = availability * .45 + (1.0 / (1.0 + latencyMs / 500.0)) * .25 + recentSuccess * .20 + eventMatch * .10
}

class PublicSourceHealthIndex(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("public_source_health", Context.MODE_PRIVATE)
    private val memory = ConcurrentHashMap<String, PublicSourceHealth>()

    init { load() }

    fun rank(eventId: String, sport: String, league: String, network: String, limit: Int = 8): List<PublicSourceHealth> =
        memory.values.asSequence()
            .filter { it.eventId == eventId || (it.sport.equals(sport, true) && (league.isBlank() || it.league.equals(league, true))) }
            .map { it.copy(eventMatch = when {
                it.eventId == eventId && eventId.isNotBlank() -> 1.0
                network.isNotBlank() && it.network.equals(network, true) -> .75
                it.sport.equals(sport, true) && it.league.equals(league, true) -> .5
                else -> .25
            }) }
            .sortedByDescending { it.score }
            .take(limit)
            .toList()

    fun rankResolved(eventId: String, sport: String, league: String, network: String, limit: Int = 8): List<PublicResolvedStream> =
        rank(eventId, sport, league, network, limit).map {
            PublicResolvedStream(it.channel, if (it.network.isBlank()) "PUBLIC" else it.network, it.url, sourceName = "Health index", latencyMs = it.latencyMs)
        }

    fun record(stream: PublicResolvedStream, sport: String, league: String, eventId: String, network: String, success: Boolean) {
        val previous = memory[stream.url]
        val availability = if (previous == null) if (success) 1.0 else 0.0 else (previous.availability * .7 + if (success) .3 else 0.0)
        val recent = if (previous == null) if (success) 1.0 else 0.0 else (previous.recentSuccess * .8 + if (success) .2 else 0.0)
        memory[stream.url] = PublicSourceHealth(stream.url, stream.name, network, sport, league, eventId, availability, stream.latencyMs, recent, 1.0, System.currentTimeMillis())
        save()
    }

    fun prune(maxAgeMs: Long = 7L * 24 * 60 * 60 * 1000) {
        val cutoff = System.currentTimeMillis() - maxAgeMs
        memory.entries.removeIf { it.value.checkedAt < cutoff }
        save()
    }

    private fun save() {
        val array = JSONArray()
        memory.values.forEach { h -> array.put(JSONObject().apply {
            put("url", h.url); put("channel", h.channel); put("network", h.network); put("sport", h.sport); put("league", h.league); put("eventId", h.eventId)
            put("availability", h.availability); put("latencyMs", h.latencyMs); put("recentSuccess", h.recentSuccess); put("eventMatch", h.eventMatch); put("checkedAt", h.checkedAt)
        }) }
        prefs.edit().putString("entries", array.toString()).apply()
    }

    private fun load() {
        val array = runCatching { JSONArray(prefs.getString("entries", "[]")) }.getOrNull() ?: return
        for (i in 0 until array.length()) runCatching {
            val o = array.getJSONObject(i)
            val h = PublicSourceHealth(o.getString("url"), o.optString("channel"), o.optString("network"), o.optString("sport"), o.optString("league"), o.optString("eventId"), o.optDouble("availability"), o.optInt("latencyMs"), o.optDouble("recentSuccess"), o.optDouble("eventMatch", 1.0), o.optLong("checkedAt"))
            memory[h.url] = h
        }
    }
}
