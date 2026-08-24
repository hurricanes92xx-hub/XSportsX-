package com.xsportsx.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.browser.customtabs.CustomTabsIntent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Secure phone/TV pairing helper. The QR contains only a short-lived pairing URI. */
object PairingClient {
    data class PairStart(val pairCode: String, val sessionId: String, val qrPayload: String, val expiresIn: Int)

    suspend fun start(pairingBaseUrl: String): PairStart = withContext(Dispatchers.IO) {
        val c = URL(pairingBaseUrl.trimEnd('/') + "/pair/start").openConnection() as HttpURLConnection
        c.requestMethod = "GET"; c.connectTimeout = 8000; c.readTimeout = 8000
        val text = c.inputStream.bufferedReader().use { it.readText() }
        val j = JSONObject(text)
        PairStart(j.getString("pairCode"), j.getString("sessionId"), j.getString("qrPayload"), j.getInt("expiresIn"))
    }

    suspend fun approve(pairingBaseUrl: String, pairCode: String, accountToken: String): String = withContext(Dispatchers.IO) {
        val c = URL(pairingBaseUrl.trimEnd('/') + "/pair/approve").openConnection() as HttpURLConnection
        c.requestMethod = "POST"; c.doOutput = true; c.setRequestProperty("Content-Type", "application/json")
        c.outputStream.use { it.write(JSONObject().put("pairCode", pairCode).put("accountToken", accountToken).toString().toByteArray()) }
        val text = c.inputStream.bufferedReader().use { it.readText() }
        JSONObject(text).getString("deviceToken")
    }

    suspend fun complete(pairingBaseUrl: String, sessionId: String, deviceToken: String): String = withContext(Dispatchers.IO) {
        val c = URL(pairingBaseUrl.trimEnd('/') + "/pair/complete").openConnection() as HttpURLConnection
        c.requestMethod = "POST"; c.doOutput = true; c.setRequestProperty("Content-Type", "application/json")
        c.outputStream.use { it.write(JSONObject().put("sessionId", sessionId).put("deviceToken", deviceToken).toString().toByteArray()) }
        val text = c.inputStream.bufferedReader().use { it.readText() }
        JSONObject(text).getString("deviceId")
    }

    fun openPairUri(context: Context, payload: String) {
        val uri = Uri.parse(payload)
        try { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
        catch (_: Exception) { CustomTabsIntent.Builder().build().launchUrl(context, uri) }
    }
}
