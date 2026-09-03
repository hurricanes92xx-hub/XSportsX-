package com.xsportsx.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Persistent metadata index for raw M3U sources. The playlist is parsed once per refresh;
 * event resolution thereafter stays local and never reparses the remote document. */
class M3uSourceIndex(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("xsportsx_m3u_index", Context.MODE_PRIVATE)

    fun get(url: String, allowStale: Boolean = true): List<ResolvedStream> {
        val key = key(url)
        val saved = prefs.getString("data_$key", null) ?: return emptyList()
        val age = System.currentTimeMillis() - prefs.getLong("time_$key", 0L)
        if (!allowStale && age > 30 * 60 * 1000L) return emptyList()
        return runCatching {
            val array = JSONArray(saved)
            buildList {
                for (i in 0 until array.length()) {
                    val o = array.optJSONObject(i) ?: continue
                    val name = o.optString("name"); val group = o.optString("group"); val streamUrl = o.optString("url")
                    if (name.isNotBlank() && streamUrl.isNotBlank()) add(ResolvedStream(name, group, streamUrl, o.optString("icon")))
                }
            }
        }.getOrDefault(emptyList())
    }

    fun put(url: String, streams: List<ResolvedStream>) {
        val array = JSONArray()
        streams.forEach { array.put(JSONObject().put("name", it.name).put("group", it.group).put("url", it.url).put("icon", it.iconUrl)) }
        prefs.edit().putString("data_${key(url)}", array.toString()).putLong("time_${key(url)}", System.currentTimeMillis()).apply()
    }

    private fun key(value: String): String {
        val bytes = java.security.MessageDigest.getInstance("SHA-1").digest(value.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
