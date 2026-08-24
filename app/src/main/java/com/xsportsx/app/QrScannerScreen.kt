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
fun QrScannerScreen(pairingUrl: String, accountToken: String, onConnected: (String) -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("Ready to scan") }
    var busy by remember { mutableStateOf(false) }
    val scanner = rememberLauncherForActivityResult(ScanContract()) { result ->
        val payload = result.contents ?: return@rememberLauncherForActivityResult
        val pairCode = payload.substringAfterLast('/').takeIf { it.isNotBlank() } ?: return@rememberLauncherForActivityResult
        busy = true; status = "Approving this TV…"
        scope.launch {
            runCatching { PairingClient.approve(pairingUrl, pairCode, accountToken) }
                .onSuccess { token -> status = "TV approved. Finishing connection…"; PairingClient.complete(pairingUrl, "", token) }
                .onFailure { status = it.message ?: "Pairing failed" }
            busy = false
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) scanner.launch(ScanOptions().apply { setPrompt("Scan the XSportsX TV QR code"); setBeepEnabled(true) }) else status = "Camera permission is required"
    }
    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) scanner.launch(ScanOptions()) else permission.launch(Manifest.permission.CAMERA)
    }
    Box(Modifier.fillMaxSize().background(Color(0xFF07080C)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(28.dp)) {
            Text("SCAN TO CONNECT", color = Color.White, style = MaterialTheme.typography.headlineMedium)
            Spacer(Modifier.height(14.dp)); Text(status, color = Color(0xFFFF536C))
            Spacer(Modifier.height(22.dp)); if (busy) CircularProgressIndicator(color = Color(0xFFFF1744))
            Spacer(Modifier.height(20.dp)); TextButton(enabled = !busy, onClick = onCancel) { Text("CANCEL") }
        }
    }
}
