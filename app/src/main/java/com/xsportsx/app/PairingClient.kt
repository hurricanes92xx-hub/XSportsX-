package com.xsportsx.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object PairingClient {
    data class PairStart(val pairCode: String, val sessionId: String, val qrPayload: String, val expiresIn: Int)
    data class Approval(val sessionId: String, val deviceToken: String)

    private fun connection(url: String, method: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply { requestMethod = method; connectTimeout = 8000; readTimeout = 8000 }

    suspend fun start(pairingBaseUrl: String): PairStart = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/start", "GET")
        val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        PairStart(j.getString("pairCode"), j.getString("sessionId"), j.getString("qrPayload"), j.getInt("expiresIn"))
    }

    suspend fun approve(pairingBaseUrl: String, pairCode: String, accountToken: String): Approval = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/approve", "POST").apply { doOutput = true; setRequestProperty("Content-Type", "application/json") }
        c.outputStream.use { it.write(JSONObject().put("pairCode", pairCode).put("accountToken", accountToken).toString().toByteArray()) }
        val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        Approval(j.getString("sessionId"), j.getString("deviceToken"))
    }

    suspend fun complete(pairingBaseUrl: String, sessionId: String, deviceToken: String): String = withContext(Dispatchers.IO) {
        val c = connection(pairingBaseUrl.trimEnd('/') + "/pair/complete", "POST").apply { doOutput = true; setRequestProperty("Content-Type", "application/json") }
        c.outputStream.use { it.write(JSONObject().put("sessionId", sessionId).put("deviceToken", deviceToken).toString().toByteArray()) }
        val j = c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        j.getString("deviceId")
    }

    fun openPairUri(context: Context, payload: String) {
        val uri = Uri.parse(payload)
        try { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
        catch (_: Exception) { CustomTabsIntent.Builder().build().launchUrl(context, uri) }
    }
}
