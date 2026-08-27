package com.xsportsx.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL

private data class PublicResolvedStream(val url:String,val title:String,val group:String,val latencyMs:Int=0)

object PublicSourceResolver {
    private const val MAX_PLAYLIST_BYTES = 4_000_000
    private val registryHosts = setOf("raw.githubusercontent.com", "github.com", "gist.githubusercontent.com")
    private val REGISTRY_URLS = listOf<String>()
    private val sportsTerms = Regex("football|basketball|baseball|hockey|soccer|ufc|boxing|rugby|volleyball|wrestling|motogp|formula|nascar|racing|sports", RegexOption.IGNORE_CASE)

    private suspend fun health(stream: PublicResolvedStream): PublicResolvedStream? = withContext(Dispatchers.IO) {
        runCatching {
            val started = System.currentTimeMillis(); val c = URL(stream.url).openConnection() as HttpURLConnection
            c.requestMethod = "GET"; c.connectTimeout = 3000; c.readTimeout = 3500; c.instanceFollowRedirects = true
            c.setRequestProperty("User-Agent", "XSportsX-public-health/1.0"); c.setRequestProperty("Accept", "application/vnd.apple.mpegurl,application/x-mpegURL,video/*,*/*")
            val code = c.responseCode
            if (code !in 200..299) { c.disconnect(); return@runCatching null }
            val type = c.contentType.orEmpty(); val input = BufferedInputStream(c.inputStream); val buffer = ByteArray(4096); val count = input.read(buffer)
            input.close(); c.disconnect(); if (count <= 0) return@runCatching null
            val prefix = String(buffer, 0, count, Charsets.UTF_8)
            if (!(type.contains("mpegurl", true) || type.contains("video", true) || type.contains("octet-stream", true) || prefix.contains("#EXTM3U", true))) return@runCatching null
            stream.copy(latencyMs = (System.currentTimeMillis() - started).toInt())
        }.getOrNull()
    }

    private fun isSports(name: String, group: String): Boolean = sportsTerms.containsMatchIn("$name $group")
    private fun isAllowedRegistryUrl(target: String): Boolean = runCatching { val uri = URL(target); uri.protocol.equals("https", true) && registryHosts.any { host -> uri.host.equals(host, true) || uri.host.endsWith(".$host", true) } }.getOrDefault(false)
    private fun isAllowedStream(target: String): Boolean = runCatching { URL(target).protocol.equals("https", true) }.getOrDefault(false)

    private suspend fun fetchRegistry(): String? {
        for (target in REGISTRY_URLS) {
            val value = fetchText(target, 256_000, registryOnly = true)
            if (value != null) return value
        }
        return null
    }

    private suspend fun fetchText(target: String, maxBytes: Int = MAX_PLAYLIST_BYTES, registryOnly: Boolean = false): String? = withContext(Dispatchers.IO) {
        runCatching {
            if (registryOnly && !isAllowedRegistryUrl(target)) return@runCatching null
            if (!registryOnly && !isAllowedStream(target)) return@runCatching null
            val c = URL(target).openConnection() as HttpURLConnection
            c.requestMethod = "GET"; c.connectTimeout = 5000; c.readTimeout = 10000; c.instanceFollowRedirects = true
            c.setRequestProperty("User-Agent", "XSportsX-public-registry/1.0"); c.setRequestProperty("Accept", "application/json,application/vnd.apple.mpegurl,application/x-mpegURL,text/plain,*/*")
            val code = c.responseCode; if (code !in 200..299) { c.disconnect(); return@runCatching null }
            val input = BufferedInputStream(c.inputStream); val out = StringBuilder(); val buffer = ByteArray(8192); var total = 0
            while (true) { val n = input.read(buffer); if (n <= 0) break; total += n; if (total > maxBytes) break; out.append(String(buffer, 0, n, Charsets.UTF_8)) }
            input.close(); c.disconnect(); out.toString()
        }.getOrNull()
    }
}
