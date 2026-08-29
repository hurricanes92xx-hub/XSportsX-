package com.xsportsx.app

import androidx.activity.compose.BackHandler
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
fun LocalQrPairingScreen(onConnected: () -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val connectedCallback by rememberUpdatedState(onConnected)
    val host = remember(context) {
        LocalPairingHost(context) { connectedCallback() }
    }
    var info by remember { mutableStateOf<LocalPairingHost.Info?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        val result = withContext(Dispatchers.IO) { host.start() }
        if (result == null) error = "TV must be connected to Wi-Fi before pairing."
        else info = result
    }

    DisposableEffect(Unit) {
        onDispose { host.stop() }
    }

    BackHandler(enabled = true) { host.stop(); onCancel() }

    Box(Modifier.fillMaxSize().background(Color(0xFF03060B)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Text("X", color = Color(0xFFFF1838), fontSize = 58.sp, fontWeight = FontWeight.Black)
            Text("CONNECT THIS TV", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Black)
            Text(
                if (info != null) "Scan this code with your XSportsX phone app"
                else "Preparing secure local pairing…",
                color = Color(0xFF8993A2), fontSize = 14.sp
            )
            Spacer(Modifier.height(28.dp))
            Box(
                Modifier.size(280.dp).background(Color.White, RoundedCornerShape(24.dp)).padding(10.dp),
                contentAlignment = Alignment.Center
            ) {
                info?.let { QrImage(it.qrPayload, Modifier.fillMaxSize()) }
                    ?: CircularProgressIndicator(color = Color(0xFFFF1838))
            }
            Spacer(Modifier.height(18.dp))
            info?.let {
                Text("CODE ${it.code}", color = Color.White, fontWeight = FontWeight.Bold)
                Text("LOCAL TV: ${it.address}:${it.port}", color = Color(0xFF7F8998), fontSize = 11.sp)
                Text("Your Xtream/M3U credentials never leave your LAN.", color = Color(0xFF626976), fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp))
            }
            error?.let { Text(it, color = Color(0xFFFF536C), modifier = Modifier.padding(top = 12.dp)) }
            Spacer(Modifier.height(18.dp))
            TextButton(onClick = { host.stop(); onCancel() }) { Text("CANCEL") }
        }
    }
}
