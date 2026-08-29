package com.xsportsx.app

import android.content.Context
import android.util.Base64
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

data class SourceConfig(
    val type: String = "XTREAM",
    val server: String = "",
    val username: String = "",
    val password: String = "",
    val m3uUrl: String = ""
) {
    fun isConfigured(): Boolean = if (type == "M3U") m3uUrl.isNotBlank()
    else server.isNotBlank() && username.isNotBlank() && password.isNotBlank()
}

class SourceStore(context: Context) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("xsportsx_source", Context.MODE_PRIVATE)
    private val keystoreAlias = "xsportsx_source_v2"

    private val key: SecretKey? by lazy { runCatching { getOrCreateKey() }.getOrNull() }
    private val legacyKey: SecretKeySpec by lazy {
        val raw = MessageDigest.getInstance("SHA-256")
            .digest((appContext.packageName + ":xsportsx-source-v1").toByteArray(StandardCharsets.UTF_8))
        SecretKeySpec(raw, "AES")
    }

    fun load(): SourceConfig {
        val config = SourceConfig(
            type = prefs.getString("type", "XTREAM") ?: "XTREAM",
            server = prefs.getString("server", "") ?: "",
            username = prefs.getString("username", "") ?: "",
            password = decrypt(prefs.getString("password", null)),
            m3uUrl = decrypt(prefs.getString("m3u", null))
        )
        if (config.isConfigured() && prefs.getString("storage_version", "1") != "3") {
            runCatching { save(config) }
        }
        return config
    }

    fun save(config: SourceConfig) {
        val normalized = config.copy(
            type = config.type.uppercase(),
            server = config.server.trim().removeSuffix("/"),
            username = config.username.trim(),
            password = config.password.trim(),
            m3uUrl = config.m3uUrl.trim()
        )
        require(normalized.isConfigured()) { "Source configuration is incomplete" }

        // Store a Keystore copy plus a compatibility copy. Some Android TV firmware
        // can invalidate/recreate Keystore keys across APK updates, which previously
        // made a saved source look signed out even though the connection had worked.
        val editor = prefs.edit()
            .putString("type", normalized.type)
            .putString("server", normalized.server)
            .putString("username", normalized.username)
            .putString("password", encryptWithKey(normalized.password, key ?: legacyKey))
            .putString("m3u", encryptWithKey(normalized.m3uUrl, key ?: legacyKey))
            .putString("compat_password", encryptWithKey(normalized.password, legacyKey))
            .putString("compat_m3u", encryptWithKey(normalized.m3uUrl, legacyKey))
            .putString("storage_version", "3")
            .putLong("saved_at", System.currentTimeMillis())
        check(editor.commit()) { "Could not persist source configuration" }

        // Verify immediately. This prevents the UI from reporting a successful
        // connection when the persisted credentials cannot actually be read back.
        val verify = load()
        check(verify.isConfigured()) { "Source was saved but could not be verified" }
    }

    fun clear() { prefs.edit().clear().commit() }

    private fun getOrCreateKey(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(keystoreAlias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance("AES", "AndroidKeyStore")
        generator.init(android.security.keystore.KeyGenParameterSpec.Builder(
            keystoreAlias,
            android.security.keystore.KeyProperties.PURPOSE_ENCRYPT or
                android.security.keystore.KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build())
        return generator.generateKey()
    }

    private fun encryptWithKey(value: String, secret: SecretKey): String {
        if (value.isBlank()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secret)
        return Base64.encodeToString(cipher.iv + cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8)), Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String?): String {
        if (encoded.isNullOrBlank()) return ""
        key?.let { decryptWithKey(encoded, it)?.let { value -> return value } }
        return decryptWithKey(prefs.getString("compat_password", null), legacyKey)
            ?: decryptWithKey(prefs.getString("compat_m3u", null), legacyKey)
            ?: decryptWithKey(encoded, legacyKey).orEmpty()
    }

    private fun decryptWithKey(encoded: String?, secretKey: SecretKey): String? = runCatching {
        if (encoded.isNullOrBlank()) return@runCatching null
        val blob = Base64.decode(encoded, Base64.NO_WRAP)
        require(blob.size > 12)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secretKey, GCMParameterSpec(128, blob, 0, 12))
        String(cipher.doFinal(blob, 12, blob.size - 12), StandardCharsets.UTF_8)
    }.getOrNull()
}
