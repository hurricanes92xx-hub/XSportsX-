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
    fun isConfigured(): Boolean = if (type == "M3U") {
        m3uUrl.isNotBlank()
    } else {
        server.isNotBlank() && username.isNotBlank() && password.isNotBlank()
    }
}

class SourceStore(context: Context) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("xsportsx_source", Context.MODE_PRIVATE)
    private val keystoreAlias = "xsportsx_source_v2"

    /**
     * Credentials must survive activity/process recreation and normal APK updates.
     * v1 used a package-name-derived AES key; v2 uses Android Keystore so the key is
     * stable for this installation and is not derivable from the application id.
     */
    private val key: SecretKey by lazy { getOrCreateKey() }
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

        // One-time migration of v1 encrypted credentials to the Keystore-backed format.
        // This is intentionally best-effort so an old install never loses a usable source.
        if (config.isConfigured() && prefs.getString("storage_version", "1") != "2") {
            save(config)
        }
        return config
    }

    fun save(config: SourceConfig) {
        val normalized = config.copy(
            server = config.server.trim().removeSuffix("/"),
            username = config.username.trim(),
            password = config.password.trim(),
            m3uUrl = config.m3uUrl.trim()
        )

        // commit() is deliberate: callers navigate away immediately after saving and
        // must not observe a stale SharedPreferences snapshot during that transition.
        prefs.edit()
            .putString("type", normalized.type)
            .putString("server", normalized.server)
            .putString("username", normalized.username)
            .putString("password", encrypt(normalized.password))
            .putString("m3u", encrypt(normalized.m3uUrl))
            .putString("storage_version", "2")
            .putLong("saved_at", System.currentTimeMillis())
            .commit()
    }

    fun clear() {
        prefs.edit().clear().commit()
    }

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

    private fun encrypt(value: String): String {
        if (value.isBlank()) return ""
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        return Base64.encodeToString(iv + ciphertext, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String?): String {
        if (encoded.isNullOrBlank()) return ""
        return decryptWithKey(encoded, key) ?: decryptWithKey(encoded, legacyKey).orEmpty()
    }

    private fun decryptWithKey(encoded: String, secretKey: SecretKey): String? = runCatching {
        val blob = Base64.decode(encoded, Base64.NO_WRAP)
        require(blob.size > 12)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secretKey, GCMParameterSpec(128, blob, 0, 12))
        String(cipher.doFinal(blob, 12, blob.size - 12), StandardCharsets.UTF_8)
    }.getOrNull()
}
