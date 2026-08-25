package com.xsportsx.app

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
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
    private const val MAX_DOWNLOAD_MS = 900_000L

    suspend fun check(context: Context): AppUpdate? = withContext(Dispatchers.IO) {
        runCatching {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            val currentCode = info.longVersionCode
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

            // Fallback only when the tiny manifest does not advertise a newer build.
            val release = JSONObject(http(RELEASE_URL))
            val tag = release.optString("tag_name", "").removePrefix("v")
            val notes = release.optString("body").ifBlank { "Performance and schedule improvements." }
            val metadataCode = Regex("XSportsX-Update-Version-Code\\s*:\\s*(\\d+)")
                .find(notes)?.groupValues?.getOrNull(1)?.toLongOrNull()
            val remoteCode = release.optLong("version_code", 0L).takeIf { it > 0L } ?: metadataCode ?: 0L
            val versionName = release.optString("version_name").ifBlank { tag.ifBlank { "New version" } }
            val assetName = if (BuildConfig.IS_TV_BUILD) "XSportsX-TV.apk" else "XSportsX-Mobile.apk"
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

    /** Fast/resumable OS-managed download path for both Mobile and TV. */
    suspend fun downloadAndInstall(context: Context, update: AppUpdate, onProgress: (Int) -> Unit = {}): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val dir = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "updates").apply { mkdirs() }
            val apk = File(dir, "XSportsX-${update.versionCode}.apk")
            if (apk.isFile && apk.length() >= 1024) {
                onProgress(100)
                return@runCatching apk
            }

            val tempName = "XSportsX-${update.versionCode}.apk.part"
            val temp = File(dir, tempName)
            if (temp.exists()) temp.delete()

            val request = DownloadManager.Request(Uri.parse(update.apkUrl)).apply {
                setTitle("XSportsX ${update.versionName}")
                setDescription("Downloading XSportsX update")
                setMimeType("application/vnd.android.package-archive")
                setAllowedOverMetered(true)
                setAllowedOverRoaming(true)
                setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "updates/$tempName")
            }
            val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            val downloadId = manager.enqueue(request)
            val started = System.currentTimeMillis()
            var finished = false

            while (!finished) {
                if (System.currentTimeMillis() - started > MAX_DOWNLOAD_MS) {
                    manager.remove(downloadId)
                    error("Update download timed out. Please try again.")
                }
                manager.query(DownloadManager.Query().setFilterById(downloadId)).use { cursor ->
                    if (!cursor.moveToFirst()) error("Update download disappeared")
                    when (cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))) {
                        DownloadManager.STATUS_SUCCESSFUL -> {
                            val localUri = cursor.getString(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_LOCAL_URI))
                            val downloaded = if (localUri.startsWith("file://")) File(Uri.parse(localUri).path ?: "") else temp
                            if (!downloaded.isFile || downloaded.length() < 1024) error("Downloaded APK is invalid")
                            if (apk.exists()) apk.delete()
                            if (!downloaded.renameTo(apk) && downloaded.absolutePath != apk.absolutePath) error("Unable to prepare the update package")
                            onProgress(100)
                            finished = true
                        }
                        DownloadManager.STATUS_FAILED -> {
                            val reason = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                            error("APK download failed ($reason)")
                        }
                        else -> {
                            val total = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                            val received = cursor.getLong(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                            if (total > 0L) onProgress(((received * 100L) / total).toInt().coerceIn(0, 99))
                        }
                    }
                }
                if (!finished) delay(250)
            }
            apk
        }.mapCatching { apk ->
            withContext(Dispatchers.Main) { install(context, apk) }
            Unit
        }
    }

    private fun install(context: Context, apk: File) {
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

    private fun http(target: String): String {
        val c = (URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout = 3000
            readTimeout = 5000
            requestMethod = "GET"
            instanceFollowRedirects = true
            useCaches = false
            setRequestProperty("User-Agent", "XSportsX-Updater/7")
            setRequestProperty("Accept", "application/json, application/vnd.github+json")
            setRequestProperty("X-GitHub-Api-Version", "2026-03-10")
            setRequestProperty("Cache-Control", "no-cache")
        }
        return try {
            if (c.responseCode !in 200..299) error("Update server HTTP ${c.responseCode}")
            c.inputStream.bufferedReader().use { it.readText() }
        } finally { c.disconnect() }
    }
}
