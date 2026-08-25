package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

@Composable
fun QrPairingScreen(pairingUrl: String, onDone: () -> Unit, onConnected: () -> Unit) {
    val context = LocalContext.current
    var start by remember { mutableStateOf<PairingClient.PairStart?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var connected by remember { mutableStateOf(false) }

    LaunchedEffect(pairingUrl) {
        runCatching { PairingClient.start(pairingUrl) }
            .onSuccess { start = it }
            .onFailure { error = it.message ?: "Unable to start pairing" }
    }

    LaunchedEffect(start?.sessionId) {
        val s = start ?: return@LaunchedEffect
        while (isActive && !connected) {
            val status = runCatching { PairingStatusClient.wait(pairingUrl, s.sessionId) }.getOrNull()
            if (status != null) {
                runCatching { PairingClient.complete(pairingUrl, s.sessionId, status.deviceToken) }
                    .onSuccess {
                        SourceStore(context).save(status.source)
                        PairingStore.save(context, it.deviceId)
                        connected = true
                        onConnected()
                    }
                    .onFailure { error = it.message ?: "Unable to finish TV pairing" }
                if (!connected) delay(1800)
            } else delay(1800)
        }
    }

    Box(Modifier.fillMaxSize().background(Color(0xFF03060B)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Text("X", color = Color(0xFFFF1838), fontSize = 58.sp, fontWeight = FontWeight.Black)
            Text("CONNECT THIS TV", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
            Text(if (connected) "TV connected — loading your source" else "Scan this code with your phone", color = Color(0xFF8993A2), fontSize = 14.sp)
            Spacer(Modifier.height(28.dp))
            Box(Modifier.size(280.dp).background(Color.White, RoundedCornerShape(24.dp)).padding(10.dp), contentAlignment = Alignment.Center) {
                start?.let { QrImage(it.qrPayload, Modifier.fillMaxSize()) } ?: CircularProgressIndicator(color = Color(0xFFFF1838))
            }
            Spacer(Modifier.height(18.dp))
            Text(start?.let { "CODE ${it.pairCode}" } ?: "Creating secure pairing…", color = Color.White, fontWeight = FontWeight.Bold)
            Text(start?.let { "Expires in ${it.expiresIn / 60}:${String.format("%02d", it.expiresIn % 60)}" } ?: "", color = Color(0xFFFF536C), fontWeight = FontWeight.Bold)
            error?.let { Text(it, color = Color(0xFFFF536C), modifier = Modifier.padding(top = 12.dp)) }
            Spacer(Modifier.height(18.dp))
            Text("Your Xtream/M3U credentials are never placed in the QR code.", color = Color(0xFF626976), fontSize = 11.sp)
            TextButton(onClick = onDone) { Text("CANCEL") }
        }
    }
}
