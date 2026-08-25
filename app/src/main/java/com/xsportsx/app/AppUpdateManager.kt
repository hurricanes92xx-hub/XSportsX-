package com.xsportsx.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

data class AppUpdate(val versionCode: Int, val versionName: String, val apkUrl: String, val notes: String)

object AppUpdateManager {
    private const val RELEASE_URL = "https://api.github.com/repos/hurricanes92xx-hub/XSportsX-/releases/latest"
    private const val MANIFEST_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/update.json"
    private const val MAX_DOWNLOAD_MS = 180_000L

    suspend fun check(context: Context): AppUpdate? = withContext(Dispatchers.IO) {
        runCatching {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            val currentCode = info.longVersionCode
            val assetName = if (BuildConfig.IS_TV_BUILD) "XSportsX-TV.apk" else "XSportsX-Mobile.apk"

            // Fast path: the tiny CDN-backed manifest avoids the much larger GitHub API response.
            val manifest = runCatching { JSONObject(http(MANIFEST_URL)) }.getOrNull()
            val manifestCode = manifest?.optLong("versionCode", 0L) ?: 0L
            val manifestUrl = if (BuildConfig.IS_TV_BUILD) {
                manifest?.optString("tvApkUrl", "").orEmpty().ifBlank { manifest?.optString("apkUrl", "").orEmpty() }
            } else {
                manifest?.optString("mobileApkUrl", "").orEmpty().ifBlank { manifest?.optString("apkUrl", "").orEmpty() }
            }
            if (manifestCode > currentCode && manifestUrl.isNotBlank()) {
                return@runCatching AppUpdate(
                    manifestCode.coerceAtMost(Int.MAX_VALUE.toLong()).toInt(),
                    manifest?.optString("versionName", "New version") ?: "New version",
                    manifestUrl,
                    manifest?.optString("notes", "Update available") ?: "Update available"
                )
            }

            // Fallback for releases while the manifest/CDN is propagating.
            val release = JSONObject(http(RELEASE_URL))
            val tag = release.optString("tag_name", "").removePrefix("v")
            val notes = release.optString("body").ifBlank { "Performance and schedule improvements." }
            val metadataCode = Regex("XSportsX-Update-Version-Code\\s*:\\s*(\\d+)")
                .find(notes)?.groupValues?.getOrNull(1)?.toLongOrNull()
            val remoteCode = release.optLong("version_code", 0L).takeIf { it > 0L } ?: metadataCode ?: 0L
            val versionName = release.optString("version_name").ifBlank { tag.ifBlank { "New version" } }
            val apkUrl = findAssetUrl(release.optJSONArray("assets"), assetName)
            if (remoteCode > currentCode && apkUrl.isNotBlank()) {
                AppUpdate(
                    remoteCode.coerceAtMost(Int.MAX_VALUE.toLong()).toInt(),
                    versionName,
                    apkUrl,
                    notes
                )
            } else null
        }.getOrNull()
    }

    private fun findAssetUrl(assets: JSONArray?, name: String): String {
        if (assets == null) return ""
        for (i in 0 until assets.length()) {
            val asset = assets.optJSONObject(i) ?: continue
            if (asset.optString("name") == name) return asset.optString("browser_download_url", "").trim()
        }
        return ""
    }

    suspend fun downloadAndInstall(context: Context, update: AppUpdate, onProgress: (Int) -> Unit = {}): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val dir = File(context.cacheDir, "updates").apply { mkdirs() }
            val apk = File(dir, "XSportsX-${update.versionCode}.apk")
            val temp = File(dir, "XSportsX-${update.versionCode}.download")
            if (!apk.isFile || apk.length() < 1024) {
                download(update.apkUrl, temp, onProgress)
                if (apk.exists()) apk.delete()
                if (!temp.renameTo(apk)) error("Unable to prepare the update package")
            } else onProgress(100)

            withContext(Dispatchers.Main) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !context.packageManager.canRequestPackageInstalls()) {
                    context.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    throw IllegalStateException("Allow XSportsX to install updates, then press UPDATE again.")
                }
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apk)
                context.startActivity(Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri, "application/vnd.android.package-archive")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                })
            }
        }
    }

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout = 3000
            readTimeout = 5000
            requestMethod = "GET"
            instanceFollowRedirects = true
            useCaches = false
            setRequestProperty("User-Agent", "XSportsX-Updater/6")
            setRequestProperty("Accept", "application/json, application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2026-03-10")
            setRequestProperty("Cache-Control", "no-cache")
        }
        return try {
            if (c.responseCode !in 200..299) error("Update server HTTP ${c.responseCode}")
            c.inputStream.bufferedReader().use { it.readText() }
        } finally { c.disconnect() }
    }

    private fun download(target: String, file: File, onProgress: (Int) -> Unit) {
        if (file.exists()) file.delete()
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10000
            readTimeout = 20000
            requestMethod = "GET"
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX-Updater/6")
            setRequestProperty("Accept", "application/vnd.android.package-archive,application/octet-stream,*/*")
        }
        val started = System.currentTimeMillis()
        try {
            if (c.responseCode !in 200..299) error("APK download HTTP ${c.responseCode}")
            val total = c.contentLengthLong
            var received = 0L
            var last = -1
            c.inputStream.buffered().use { input -> file.outputStream().buffered().use { output ->
                // Larger chunks reduce overhead on TV/mobile APK downloads.
                val buffer = ByteArray(256 * 1024)
                while (true) {
                    if (System.currentTimeMillis() - started > MAX_DOWNLOAD_MS) error("Update download timed out. Please try again.")
                    val n = input.read(buffer)
                    if (n < 0) break
                    output.write(buffer, 0, n)
                    received += n
                    val p = if (total > 0) ((received * 100L) / total).toInt().coerceIn(0, 99) else (received / 524288L).toInt().coerceAtMost(99)
                    if (p != last) { last = p; onProgress(p) }
                }
            }}
            if (!file.isFile || file.length() < 1024) error("Downloaded APK is invalid")
            onProgress(100)
        } finally { c.disconnect() }
    }
}
