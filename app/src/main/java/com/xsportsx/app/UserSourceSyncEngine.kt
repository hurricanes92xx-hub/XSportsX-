package com.xsportsx.app

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Keeps the user's authorized Xtream/M3U source warm independently of the event resolver.
 * The app can render immediately from cached provider metadata while this refresh runs.
 */
class UserSourceSyncEngine(private val context: Context) {
    private val appContext = context.applicationContext
    private val store = SourceStore(appContext)
    private val xtreamIndex = XtreamSourceIndex(appContext)
    private val m3uIndex = M3uSourceIndex(appContext)

    suspend fun syncNow(force: Boolean = true): SyncResult = withContext(Dispatchers.IO) {
        val config = store.load()
        if (!config.isConfigured()) return@withContext SyncResult("NONE", 0, false, "No authorized source configured")
        runCatching {
            when (config.type) {
                "XTREAM" -> SyncResult("XTREAM", xtreamIndex.refreshAll(config, force), true, "")
                "M3U" -> {
                    val streams = downloadM3u(config.m3uUrl)
                    m3uIndex.put(config.m3uUrl, streams)
                    SyncResult("M3U", streams.size, true, "")
                }
                else -> SyncResult(config.type, 0, false, "Unsupported source type")
            }
        }.getOrElse { SyncResult(config.type, 0, false, it.message ?: "Source refresh failed") }
    }

    private fun downloadM3u(url: String): List<ResolvedStream> {
        val result = ArrayList<ResolvedStream>()
        var name = ""
        var group = "LIVE"
        var icon = ""
        open(url).use { reader ->
            while (true) {
                val line = reader.readLine() ?: break
                val trimmed = line.trim()
                when {
                    trimmed.startsWith("#EXTINF", true) -> {
                        name = trimmed.substringAfterLast(',', "Unnamed").trim()
                        group = attr(trimmed, "group-title").ifBlank { "LIVE" }
                        icon = attr(trimmed, "tvg-logo")
                    }
                    trimmed.isNotBlank() && !trimmed.startsWith("#") -> {
                        if (name.isNotBlank()) result += ResolvedStream(name, group, trimmed, icon)
                        name = ""; group = "LIVE"; icon = ""
                    }
                }
            }
        }
        return result
    }

    private fun open(target: String): BufferedReader {
        val connection = (URL(target).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5_000
            readTimeout = 15_000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "XSportsX/3.1")
            setRequestProperty("Accept", "application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
            setRequestProperty("Accept-Encoding", "gzip")
            setRequestProperty("Connection", "keep-alive")
        }
        if (connection.responseCode !in 200..299) {
            val code = connection.responseCode
            connection.disconnect()
            error("Source returned HTTP $code")
        }
        return BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8), 64 * 1024)
    }

    private fun attr(line: String, key: String): String {
        val regex = Regex("$key=\\\"([^\\\"]*)\\\"", RegexOption.IGNORE_CASE)
        return regex.find(line)?.groupValues?.getOrNull(1).orEmpty()
    }

    data class SyncResult(val type: String, val count: Int, val success: Boolean, val error: String)

    companion object {
        private const val STARTUP_WORK = "user-source-startup-sync"
        private const val PERIODIC_WORK = "user-source-periodic-sync"

        fun schedule(context: Context) {
            val appContext = context.applicationContext
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            WorkManager.getInstance(appContext).enqueueUniqueWork(
                STARTUP_WORK,
                ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<UserSourceSyncWorker>()
                    .setConstraints(constraints)
                    .build()
            )

            WorkManager.getInstance(appContext).enqueueUniquePeriodicWork(
                PERIODIC_WORK,
                ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<UserSourceSyncWorker>(6, TimeUnit.HOURS)
                    .setConstraints(constraints)
                    .build()
            )
        }
    }
}

class UserSourceSyncWorker(
    appContext: Context,
    workerParams: androidx.work.WorkerParameters
) : CoroutineWorker(appContext, workerParams) {
    override suspend fun doWork(): Result {
        val result = UserSourceSyncEngine(applicationContext).syncNow(force = true)
        return if (result.success) Result.success() else Result.retry()
    }
}
