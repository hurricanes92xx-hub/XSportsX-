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

/** Small sideload-friendly updater. The APK must be signed with the same key as
 * the installed app; the release workflow should use one persistent signing key. */
data class AppUpdate(val versionCode:Int,val versionName:String,val apkUrl:String,val notes:String)

object AppUpdateManager {
    private const val MANIFEST_URL = "https://raw.githubusercontent.com/hurricanes92xx-hub/XSportsX-/android-app/update.json"

    suspend fun check(context:Context):AppUpdate? = withContext(Dispatchers.IO) {
        runCatching {
            val current=context.packageManager.getPackageInfo(context.packageName,0).longVersionCode
            val json=JSONObject(http(MANIFEST_URL))
            val remote=json.optInt("versionCode",0)
            if(remote<=current) return@runCatching null
            AppUpdate(remote,json.optString("versionName","New version"),json.getString("apkUrl"),json.optString("notes","Performance and schedule improvements."))
        }.getOrNull()
    }

    suspend fun downloadAndInstall(context:Context,update:AppUpdate):Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val dir=File(context.cacheDir,"updates").apply { mkdirs() }
            val apk=File(dir,"XSportsX-${update.versionCode}.apk")
            download(update.apkUrl,apk)
            val uri=FileProvider.getUriForFile(context,"${context.packageName}.fileprovider",apk)
            withContext(Dispatchers.Main) {
                if(Build.VERSION.SDK_INT>=Build.VERSION_CODES.O && !context.packageManager.canRequestPackageInstalls()) {
                    context.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")))
                    throw IllegalStateException("Allow XSportsX to install updates, then tap UPDATE again.")
                }
                val intent=Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(uri,"application/vnd.android.package-archive")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
            }
        }
    }

    private fun http(target:String):String {
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout=4000;readTimeout=7000;requestMethod="GET"
            setRequestProperty("User-Agent","XSportsX-Updater/1")
            setRequestProperty("Accept","application/json")
        }
        return try {
            if(c.responseCode !in 200..299) error("Update server HTTP ${c.responseCode}")
            c.inputStream.bufferedReader().use { it.readText() }
        } finally { c.disconnect() }
    }

    private fun download(target:String,file:File) {
        val c=(URL(target).openConnection() as HttpURLConnection).apply {
            connectTimeout=6000;readTimeout=15000;requestMethod="GET";instanceFollowRedirects=true
            setRequestProperty("User-Agent","XSportsX-Updater/1")
        }
        try {
            if(c.responseCode !in 200..299) error("APK download HTTP ${c.responseCode}")
            c.inputStream.use { input -> file.outputStream().use { output -> input.copyTo(output) } }
            if(!file.isFile || file.length()<1024) error("Downloaded APK is invalid")
        } finally { c.disconnect() }
    }
}
