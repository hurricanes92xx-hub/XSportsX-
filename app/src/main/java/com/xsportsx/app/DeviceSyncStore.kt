package com.xsportsx.app

import android.content.Context
import android.util.Base64
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class DeviceSyncStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("xsportsx_device", Context.MODE_PRIVATE)

    private fun key(): SecretKeySpec {
        val raw = MessageDigest.getInstance("SHA-256")
            .digest((context.packageName + ":xsportsx-device-v1").toByteArray())
        return SecretKeySpec(raw, "AES")
    }

    fun saveDeviceId(id: String) = save("device_id", id)
    fun deviceId(): String? = load("device_id")
    fun saveAccountToken(token: String) = save("account_token", token)
    fun accountToken(): String? = load("account_token")
    fun clear() { prefs.edit().clear().apply() }

    private fun save(name: String, value: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val blob = cipher.iv + cipher.doFinal(value.toByteArray())
        prefs.edit().putString(name, Base64.encodeToString(blob, Base64.NO_WRAP)).apply()
    }

    private fun load(name: String): String? = runCatching {
        val encoded = prefs.getString(name, null) ?: return@runCatching null
        val blob = Base64.decode(encoded, Base64.NO_WRAP)
        require(blob.size > 12) { "Invalid encrypted device data" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, blob, 0, 12))
        String(cipher.doFinal(blob, 12, blob.size - 12))
    }.getOrNull()
}
