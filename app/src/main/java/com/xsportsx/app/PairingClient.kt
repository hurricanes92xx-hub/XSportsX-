package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object PairingClient {
    data class PairStart(val pairCode: String, val sessionId: String, val qrPayload: String, val expiresIn: Int)
    data class Approval(val sessionId: String, val deviceToken: String)
    data class Completion(val sessionId: String, val deviceId: String, val sourceConfig: JSONObject)

    private fun connection(url: String, method: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 8000
            readTimeout = 8000
            setRequestProperty("Accept", "application/json")
        }

    suspend fun start(pairingBaseUrl: String): PairStart = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/start", "GET")
        try {
            val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
            PairStart(j.getString("pairCode"), j.getString("sessionId"), j.getString("qrPayload"), j.getInt("expiresIn"))
        } finally { c.disconnect() }
    }

    suspend fun approve(pairingBaseUrl: String, pairCode: String, sourceConfig: JSONObject): Approval = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/approve", "POST").apply {
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            c.outputStream.use { it.write(JSONObject().put("pairCode", pairCode).put("sourceConfig", sourceConfig).toString().toByteArray()) }
            val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
            Approval(j.getString("sessionId"), j.getString("deviceToken"))
        } finally { c.disconnect() }
    }

    suspend fun complete(pairingBaseUrl: String, sessionId: String, deviceToken: String): Completion = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/complete", "POST").apply {
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            c.outputStream.use { it.write(JSONObject().put("sessionId", sessionId).put("deviceToken", deviceToken).toString().toByteArray()) }
            val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
            Completion(j.getString("sessionId"), j.getString("deviceId"), j.getJSONObject("sourceConfig"))
        } finally { c.disconnect() }
    }
}
