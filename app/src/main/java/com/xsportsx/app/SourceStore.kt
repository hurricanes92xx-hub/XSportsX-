package com.xsportsx.app

import android.content.Context
import android.util.Base64
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

data class SourceConfig(
    val type: String = "XTREAM",
    val server: String = "",
    val username: String = "",
    val password: String = "",
    val m3uUrl: String = ""
) {
    fun isConfigured(): Boolean = if (type == "M3U") m3uUrl.isNotBlank() else server.isNotBlank() && username.isNotBlank() && password.isNotBlank()
}

class SourceStore(context: Context) {
    private val prefs = context.getSharedPreferences("xsportsx_source", Context.MODE_PRIVATE)
    private val key: SecretKeySpec by lazy {
        val raw = MessageDigest.getInstance("SHA-256")
            .digest((context.packageName + ":xsportsx-source-v1").toByteArray())
        SecretKeySpec(raw, "AES")
    }

    fun load(): SourceConfig = SourceConfig(
        type = prefs.getString("type", "XTREAM") ?: "XTREAM",
        server = prefs.getString("server", "") ?: "",
        username = prefs.getString("username", "") ?: "",
        password = decrypt(prefs.getString("password", null)),
        m3uUrl = decrypt(prefs.getString("m3u", null))
    )

    fun save(config: SourceConfig) {
        prefs.edit()
            .putString("type", config.type)
            .putString("server", config.server.trim().removeSuffix("/"))
            .putString("username", config.username.trim())
            .putString("password", encrypt(config.password))
            .putString("m3u", encrypt(config.m3uUrl))
            .apply()
    }

    fun clear() { prefs.edit().clear().apply() }

    private fun encrypt(value: String): String {
        if (value.isBlank()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        return Base64.encodeToString(cipher.iv + cipher.doFinal(value.toByteArray()), Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String?): String {
        if (encoded.isNullOrBlank()) return ""
        return runCatching {
            val blob = Base64.decode(encoded, Base64.NO_WRAP)
            require(blob.size > 12)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, blob, 0, 12))
            String(cipher.doFinal(blob, 12, blob.size - 12))
        }.getOrDefault("")
    }
}
