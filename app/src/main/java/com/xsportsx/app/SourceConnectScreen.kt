package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

@Composable
fun SourceConnectScreen(onBack: () -> Unit, onSaved: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val store = remember { SourceStore(context) }
    var config by remember { mutableStateOf(store.load()) }
    var testing by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(
        Modifier.fillMaxSize().background(Color(0xFF05060A)).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 38.sp, modifier = Modifier.clickable { onBack() })
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text("CONNECT SOURCE", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
                Text("Your authorized Xtream / M3U source powers LIVE", color = Color(0xFF737B89), fontSize = 11.sp)
            }
        }
        Spacer(Modifier.height(22.dp))

        Row(Modifier.fillMaxWidth().background(Color(0xFF0D1119), RoundedCornerShape(16.dp)).padding(5.dp)) {
            SourceTab("XTREAM", config.type == "XTREAM") { config = config.copy(type = "XTREAM") }
            SourceTab("M3U", config.type == "M3U") { config = config.copy(type = "M3U") }
        }
        Spacer(Modifier.height(18.dp))

        Column(Modifier.fillMaxWidth().widthIn(max = 620.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
            if (config.type == "XTREAM") {
                SourceField("Server URL", config.server, { config = config.copy(server = it) }, "https://provider.example")
                SourceField("Username", config.username, { config = config.copy(username = it) }, "Xtream username")
                SourceField("Password", config.password, { config = config.copy(password = it) }, "Xtream password", true)
            } else {
                SourceField("M3U playlist URL", config.m3uUrl, { config = config.copy(m3uUrl = it) }, "https://provider.example/playlist.m3u")
            }
        }

        Spacer(Modifier.height(18.dp))
        status?.let {
            Text(it, color = if (it.startsWith("Connected")) Color(0xFF63FF9A) else Color(0xFFFF6B7D), fontSize = 12.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
        }

        Button(
            onClick = {
                status = null
                val normalized = config.copy(
                    server = config.server.trim().removeSuffix("/"),
                    username = config.username.trim(),
                    password = config.password.trim(),
                    m3uUrl = config.m3uUrl.trim()
                )
                if (!normalized.isConfigured()) {
                    status = if (normalized.type == "M3U") "Enter an M3U playlist URL." else "Enter server, username and password."
                    return@Button
                }
                testing = true
                scope.launch {
                    val result = testSource(normalized)
                    if (result.ok) {
                        val saved = runCatching { store.save(normalized) }
                        if (saved.isSuccess) {
                            status = result.message
                            testing = false
                            onSaved()
                        } else {
                            testing = false
                            status = "Connection works, but could not save source. ${saved.exceptionOrNull()?.message ?: "Try again."}"
                        }
                    } else {
                        testing = false
                        status = result.message
                    }
                }
            },
            enabled = !testing,
            modifier = Modifier.fillMaxWidth().height(54.dp).semantics {
                contentDescription = if (testing) "TESTING SOURCE" else "TEST & CONNECT"
            },
            shape = RoundedCornerShape(16.dp)
        ) { Text(if (testing) "TESTING SOURCE…" else "TEST & CONNECT", fontWeight = FontWeight.Black) }

        Spacer(Modifier.height(12.dp))
        Text("Credentials are encrypted on this device. XSportsX only uses sources you provide and authorize.", color = Color(0xFF626A77), fontSize = 10.sp)
    }
}

@Composable
private fun RowScope.SourceTab(label: String, selected: Boolean, onClick: () -> Unit) {
    Box(Modifier.weight(1f).clickable { onClick() }.background(if (selected) Color(0xFFFF1744) else Color.Transparent, RoundedCornerShape(12.dp)).padding(vertical = 12.dp), contentAlignment = Alignment.Center) {
        Text(label, color = Color.White, fontWeight = FontWeight.Black, fontSize = 11.sp)
    }
}

@Composable
private fun SourceField(label: String, value: String, onValue: (String) -> Unit, placeholder: String, password: Boolean = false) {
    OutlinedTextField(
        value = value,
        onValueChange = onValue,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        placeholder = { Text(placeholder) },
        singleLine = true,
        visualTransformation = if (password) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None
    )
}

private data class SourceTestResult(val ok: Boolean, val message: String)

private suspend fun testSource(config: SourceConfig): SourceTestResult = withContext(Dispatchers.IO) {
    try {
        if (config.type == "M3U") {
            val body = get(config.m3uUrl)
            val lines = body.lineSequence().map { it.trim() }.filter { it.isNotBlank() }.toList()
            val playableUrls = lines.count { it.startsWith("http://") || it.startsWith("https://") }
            val hasPlaylist = lines.any { it.startsWith("#EXTM3U", true) || it.startsWith("#EXTINF", true) }
            if (hasPlaylist && playableUrls > 0) {
                SourceTestResult(true, "Connected • M3U playlist verified ($playableUrls streams)")
            } else {
                SourceTestResult(false, "Connected to URL, but it did not return a valid M3U playlist.")
            }
        } else {
            val base = config.server.trimEnd('/')
            val target = "$base/player_api.php?username=${URLEncoder.encode(config.username, "UTF-8")}&password=${URLEncoder.encode(config.password, "UTF-8")}"
            val body = get(target)
            val json = runCatching { JSONObject(body) }.getOrNull()
                ?: return@withContext SourceTestResult(false, "Server responded, but the Xtream API returned invalid data.")
            val userInfo = json.optJSONObject("user_info")
            val auth = userInfo?.optInt("auth", -1) ?: -1
            if (auth == 1) {
                val status = userInfo.optString("status").ifBlank { "active" }
                SourceTestResult(true, "Connected • Xtream account $status")
            } else if (auth == 0) {
                SourceTestResult(false, "Xtream rejected the username or password.")
            } else {
                SourceTestResult(false, "Server responded, but this does not look like a valid Xtream API.")
            }
        }
    } catch (e: Exception) {
        SourceTestResult(false, "Connection failed • ${e.message ?: "check source details"}")
    }
}

private fun get(target: String): String {
    val connection = (URL(target).openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 10000
        readTimeout = 15000
        instanceFollowRedirects = true
        useCaches = false
        setRequestProperty("User-Agent", "XSportsX/2.0")
        setRequestProperty("Accept", "application/json, text/plain, audio/x-mpegurl, application/vnd.apple.mpegurl, */*")
        setRequestProperty("Connection", "close")
    }
    return try {
        val code = connection.responseCode
        if (code !in 200..299) error("Source returned HTTP $code")
        connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    } finally {
        connection.disconnect()
    }
}
