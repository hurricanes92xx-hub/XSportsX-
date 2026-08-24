package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun QrPairingScreen(pairingUrl: String, onDone: () -> Unit) {
    var start by remember { mutableStateOf<PairingClient.PairStart?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(pairingUrl) {
        runCatching { PairingClient.start(pairingUrl) }
            .onSuccess { start = it }
            .onFailure { error = it.message ?: "Unable to start pairing" }
    }
    Box(Modifier.fillMaxSize().background(Color(0xFF07080C)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Text("X", color = Color(0xFFFF1744), fontSize = 58.sp, fontWeight = FontWeight.Black)
            Text("CONNECT THIS TV", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
            Text("Scan this code with your signed-in phone", color = Color(0xFF8C93A1), fontSize = 14.sp)
            Spacer(Modifier.height(28.dp))
            Box(Modifier.size(260.dp).background(Color.White, RoundedCornerShape(24.dp)), contentAlignment = Alignment.Center) {
                // QR rendering is supplied by the app's QR library from start.qrPayload.
                Text(start?.pairCode ?: "LOADING", color = Color.Black, fontSize = 22.sp, fontWeight = FontWeight.Black)
            }
            Spacer(Modifier.height(18.dp))
            Text(start?.let { "Expires in ${it.expiresIn / 60}:${String.format("%02d", it.expiresIn % 60)}" } ?: "Creating secure pairing…", color = Color(0xFFFF536C), fontWeight = FontWeight.Bold)
            error?.let { Text(it, color = Color(0xFFFF536C), modifier = Modifier.padding(top = 12.dp)) }
            Spacer(Modifier.height(22.dp))
            Text("Your Xtream/M3U credentials are never placed in the QR code.", color = Color(0xFF626976), fontSize = 11.sp)
            TextButton(onClick = onDone) { Text("CANCEL") }
        }
    }
}
