package com.xsportsx.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** Reliable sideload updater. The downloaded APK must be signed with the same key as the installed app. */
data class AppUpdate(val versionCode:Int,val versionName:String,val apkUrl:String,val notes:String)

object AppUpdateManager {
    private const val MANIFEST_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/update.json"
    private const val MAX_DOWNLOAD_MS = 180_000L

    suspend fun check(context:Context):AppUpdate? = withContext(Dispatchers.IO) {
        runCatching {
            val current = context.packageManager.getPackageInfo(context.packageName,0).longVersionCode
            val json = JSONObject(http("$MANIFEST_URL?ts=${System.currentTimeMillis()}"))
            val remote = json.optLong("versionCode",0L)
            if(remote <= current) return@runCatching null
            val apkUrl = json.optString("apkUrl","").trim()
            if(apkUrl.isBlank()) error("Update package is not available yet")
            AppUpdate(remote.toInt(), json.optString("versionName","New version"), apkUrl,
                json.optString("notes","Performance and schedule improvements."))
        }.getOrNull()
    }

    suspend fun downloadAndInstall(
        context:Context,
        update:AppUpdate,
        onProgress:(Int)->Unit = {}
    ):Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val dir = File(context.cacheDir,"updates").apply { mkdirs() }
            val apk = File(dir,"XSportsX-${update.versionCode}.apk")
            val temp = File(dir,"XSportsX-${update.versionCode}.download")

            if(!apk.isFile || apk.length() < 1024) {
                download(update.apkUrl,temp,onProgress)
                if(apk.exists()) apk.delete()
                if(!temp.renameTo(apk)) error("Unable to prepare the update package")
            } else {
                onProgress(100)
            }

            withContext(Dispatchers.Main) {
                if(Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                    !context.packageManager.canRequestPackageInstalls()) {
                    context.startActivity(
                        Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                            Uri.parse("package:${context.packageName}"))
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    )
                    throw IllegalStateException("Allow XSportsX to install updates, then press UPDATE again.")
                }

                val uri = FileProvider.getUriForFile(context,"${context.packageName}.fileprovider",apk)
                val intent = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri,"application/vnd.android.package-archive")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
                context.startActivity(intent)
            }
        }
    }

    private fun http(target:String):String {
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout=5000; readTimeout=8000; requestMethod="GET"; instanceFollowRedirects=true
            setRequestProperty("User-Agent","XSportsX-Updater/3")
            setRequestProperty("Accept","application/json")
            setRequestProperty("Cache-Control","no-cache")
            setRequestProperty("Pragma","no-cache")
        }
        return try {
            if(c.responseCode !in 200..299) error("Update server HTTP ${c.responseCode}")
            c.inputStream.bufferedReader().use { it.readText() }
        } finally { c.disconnect() }
    }

    private fun download(target:String,file:File,onProgress:(Int)->Unit) {
        if(file.exists()) file.delete()
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout=10000; readTimeout=20000; requestMethod="GET"; instanceFollowRedirects=true
            setRequestProperty("User-Agent","Mozilla/5.0 XSportsX-Updater/3")
            setRequestProperty("Accept","application/vnd.android.package-archive,application/octet-stream,*/*")
            setRequestProperty("Cache-Control","no-cache")
        }
        val started=System.currentTimeMillis()
        try {
            if(c.responseCode !in 200..299) error("APK download HTTP ${c.responseCode}")
            val total=c.contentLengthLong
            var received=0L
            var lastProgress=-1
            c.inputStream.buffered().use { input ->
                file.outputStream().buffered().use { output ->
                    val buffer=ByteArray(32*1024)
                    while(true) {
                        if(System.currentTimeMillis()-started > MAX_DOWNLOAD_MS) error("Update download timed out. Please try again.")
                        val n=input.read(buffer)
                        if(n < 0) break
                        output.write(buffer,0,n)
                        received += n
                        if(total > 0) {
                            val p=((received*100L)/total).toInt().coerceIn(0,99)
                            if(p != lastProgress) { lastProgress=p; onProgress(p) }
                        } else {
                            val p=(received/524288L).toInt().coerceAtMost(99)
                            if(p != lastProgress) { lastProgress=p; onProgress(p) }
                        }
                    }
                    output.flush()
                }
            }
            if(!file.isFile || file.length()<1024) error("Downloaded APK is invalid")
            onProgress(100)
        } finally { c.disconnect() }
    }
}
