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
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.compose.ui.platform.LocalContext
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import kotlinx.coroutines.launch

@Composable
fun PhonePairScanner(pairingBaseUrl: String, accountToken: String, onConnected: (String) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("Scan the QR code on your TV") }
    var busy by remember { mutableStateOf(false) }

    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val raw = result.contents ?: return@rememberLauncherForActivityResult
        val code = raw.substringAfter("xsportsx://pair/", raw).substringBefore('?').trim()
        if (code.isBlank()) { status = "That isn't an XSportsX pairing code"; return@rememberLauncherForActivityResult }
        busy = true
        scope.launch {
            runCatching { PairingClient.approve(pairingBaseUrl, code, accountToken) }
                .onSuccess { deviceToken ->
                    status = "TV approved — completing connection…"
                    // The TV completes the session after receiving its one-time token.
                    onConnected(deviceToken)
                }
                .onFailure { status = it.message ?: "Pairing failed or expired" }
            busy = false
        }
    }

    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scanner.launch(ScanOptions().apply { setPrompt("Scan the XSportsX TV QR code") })
        else status = "Camera permission is required to scan the TV code"
    }

    Box(Modifier.fillMaxSize().background(Color(0xFF07080C)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(28.dp)) {
            Text("XSportsX", color = Color.White, style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(10.dp))
            Text("CONNECT TV", color = Color(0xFFFF1744), style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(20.dp))
            Text(status, color = Color(0xFFB9BFCA))
            Spacer(Modifier.height(28.dp))
            Button(enabled = !busy, onClick = {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
                    scanner.launch(ScanOptions().apply { setPrompt("Scan the XSportsX TV QR code") })
                else permission.launch(Manifest.permission.CAMERA)
            }) { Text(if (busy) "CONNECTING…" else "SCAN TV QR CODE") }
        }
    }
}
