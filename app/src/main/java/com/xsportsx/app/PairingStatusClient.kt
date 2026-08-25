package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class PairingStatus(val deviceToken: String, val source: SourceConfig)

object PairingStatusClient {
    suspend fun wait(baseUrl: String, sessionId: String): PairingStatus? = withContext(Dispatchers.IO) {
        val url = URL(baseUrl.trimEnd('/') + "/pair/status?sessionId=" + java.net.URLEncoder.encode(sessionId, "UTF-8"))
        val c = url.openConnection() as HttpURLConnection
        c.requestMethod = "GET"
        c.connectTimeout = 5000
        c.readTimeout = 5000
        try {
            if (c.responseCode != 200) return@withContext null
            val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
            if (!j.optBoolean("approved", false)) return@withContext null
            val s = j.optJSONObject("sourceConfig") ?: return@withContext null
            PairingStatus(
                deviceToken = j.getString("deviceToken"),
                source = SourceConfig(
                    type = s.optString("type", "XTREAM").uppercase(),
                    server = s.optString("server", ""),
                    username = s.optString("username", ""),
                    password = s.optString("password", ""),
                    m3uUrl = s.optString("m3uUrl", "")
                )
            )
        } finally { c.disconnect() }
    }
}
