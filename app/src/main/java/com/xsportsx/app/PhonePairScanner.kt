package com.xsportsx.app

import android.Manifest
import android.content.pm.PackageManager
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
import kotlinx.coroutines.launch
import org.json.JSONObject

@Composable
fun PhonePairScanner(pairingBaseUrl: String, onConnected: (String) -> Unit, onCancel: () -> Unit = {}) {
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

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val raw = result.contents ?: return@rememberLauncherForActivityResult
        val code = raw.substringAfter("xsportsx://pair/", raw).substringBefore('?').trim()
        if (code.isBlank()) { status = "That isn't an XSportsX pairing code"; return@rememberLauncherForActivityResult }
        busy = true
        scope.launch {
            runCatching { PairingClient.approve(pairingBaseUrl, code, sourceJson()) }
                .onSuccess {
                    PairingStore.save(context, "paired-tv:${it.sessionId}")
                    status = "TV connected"
                    onConnected(it.sessionId)
                }
                .onFailure { status = it.message ?: "Pairing failed or expired" }
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
