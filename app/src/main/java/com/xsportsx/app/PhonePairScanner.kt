package com.xsportsx.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

@Composable
fun PhonePairScanner(onConnected: (String) -> Unit, onCancel: () -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val source = remember { SourceStore(context).load() }
    var status by remember { mutableStateOf("Scan the QR code on your TV") }
    var busy by remember { mutableStateOf(false) }

    fun sourceJson() = JSONObject().apply {
        put("type", source.type)
        put("server", source.server)
        put("username", source.username)
        put("password", source.password)
        put("m3uUrl", source.m3uUrl)
    }

    suspend fun approveLocal(raw: String) = withContext(Dispatchers.IO) {
        val uri = Uri.parse(raw)
        require(uri.scheme == "http" && uri.path == "/pair" && !uri.getQueryParameter("code").isNullOrBlank()) {
            "Scan the QR code shown by the XSportsX TV app"
        }

        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        val network = cm?.activeNetwork
        var lastError: Throwable? = null
        repeat(2) { attempt ->
            val connection = runCatching {
                val rawConnection = if (network != null) {
                    network.openConnection(URL(raw))
                } else {
                    URL(raw).openConnection()
                }
                (rawConnection as HttpURLConnection).apply {
                    requestMethod = "POST"
                    doOutput = true
                    connectTimeout = 5000
                    readTimeout = 8000
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Connection", "close")
                }
            }.getOrElse {
                lastError = it
                return@repeat
            }

            try {
                connection.outputStream.use { it.write(sourceJson().toString().toByteArray(Charsets.UTF_8)) }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (code !in 200..299) {
                    throw IllegalStateException(JSONObject(body.ifBlank { "{}" }).optString("error", "TV pairing failed ($code)"))
                }
                if (!JSONObject(body.ifBlank { "{}" }).optBoolean("ok", false)) throw IllegalStateException("TV did not accept the source")
                return@withContext true
            } catch (t: Throwable) {
                lastError = t
            } finally {
                connection.disconnect()
            }
            if (attempt == 0) kotlinx.coroutines.delay(350)
        }
        throw IllegalStateException(
            lastError?.message?.takeIf { it.isNotBlank() }
                ?: "Could not reach the TV. Make sure both devices are on the same Wi-Fi network and allow XSportsX to access nearby devices."
        )
    }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val raw = result.contents ?: return@rememberLauncherForActivityResult
        busy = true
        scope.launch {
            runCatching { approveLocal(raw) }
                .onSuccess {
                    val uri = Uri.parse(raw)
                    PairingStore.save(context, "paired-tv:local:${uri.host}:${uri.port}")
                    status = "TV connected"
                    onConnected("local")
                }
                .onFailure { status = it.message ?: "Local TV pairing failed" }
            busy = false
        }
    }

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scanner.launch(ScanOptions().apply { setPrompt("Scan the XSportsX TV QR code") })
        else status = "Camera permission is required to scan the TV code"
    }

    Box(Modifier.fillMaxSize().background(Color(0xFF03060B)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(28.dp)) {
            Text("XSPORTSX", color = Color.White, style = MaterialTheme.typography.headlineLarge)
            Text("CONNECT TV", color = Color(0xFFFF1838), style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(20.dp))
            Text(status, color = Color(0xFFB9BFCA))
            Spacer(Modifier.height(28.dp))
            Button(enabled = !busy && source.isConfigured(), onClick = {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
                    scanner.launch(ScanOptions().apply { setPrompt("Scan the XSportsX TV QR code") })
                else permission.launch(Manifest.permission.CAMERA)
            }) { Text(if (busy) "CONNECTING…" else "SCAN TV QR CODE") }
            if (!source.isConfigured()) Text("Connect a source on this phone first.", color = Color(0xFFFF6B7D), modifier = Modifier.padding(top = 12.dp))
            TextButton(onClick = onCancel) { Text("CANCEL") }
        }
    }
}
