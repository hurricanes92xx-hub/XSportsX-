package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val ConnectBg = Color(0xFF03060B)
private val ConnectPanel = Color(0xFF0B111A)
private val ConnectRed = Color(0xFFFF1838)
private val ConnectMuted = Color(0xFF8993A2)

@Composable
fun TvSourceChooser(onQr: () -> Unit, onManual: () -> Unit, onBack: () -> Unit) {
    Box(Modifier.fillMaxSize().background(ConnectBg)) {
        Column(
            Modifier.fillMaxSize().padding(horizontal = 70.dp, vertical = 42.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("CONNECT YOUR SOURCE", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Black)
            Spacer(Modifier.height(8.dp))
            Text("Choose the easiest way to sign in on this TV", color = ConnectMuted, fontSize = 13.sp)
            Spacer(Modifier.height(34.dp))
            Row(Modifier.fillMaxWidth().widthIn(max = 900.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                ConnectOption(
                    title = "SCAN QR CODE",
                    subtitle = "Use your phone to securely connect Xtream or M3U",
                    icon = "▦",
                    accent = true,
                    onClick = onQr,
                    modifier = Modifier.weight(1f)
                )
                ConnectOption(
                    title = "SIGN IN ON TV",
                    subtitle = "Enter Xtream username/password or an M3U URL",
                    icon = "⌨",
                    accent = false,
                    onClick = onManual,
                    modifier = Modifier.weight(1f)
                )
            }
            Spacer(Modifier.height(28.dp))
            FocusButton("CANCEL", onBack)
            Spacer(Modifier.weight(1f))
            Text("Xtream Codes and M3U credentials are stored encrypted on this device.", color = Color(0xFF626976), fontSize = 10.sp)
        }
    }
}

@Composable
private fun ConnectOption(title: String, subtitle: String, icon: String, accent: Boolean, onClick: () -> Unit, modifier: Modifier) {
    var focused by remember { mutableStateOf(false) }
    Box(
        modifier
            .height(230.dp)
            .clip(RoundedCornerShape(24.dp))
            .background(if (focused || accent) Color(0xFF101821) else ConnectPanel)
            .border(2.dp, if (focused || accent) ConnectRed else Color(0xFF26303D), RoundedCornerShape(24.dp))
            .onFocusChanged { focused = it.isFocused }
            .focusable()
            .clickable { onClick() }
            .padding(28.dp)
    ) {
        Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(icon, color = if (focused || accent) ConnectRed else Color.White, fontSize = 52.sp, fontWeight = FontWeight.Black)
            Spacer(Modifier.height(12.dp))
            Text(title, color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)
            Spacer(Modifier.height(8.dp))
            Text(subtitle, color = ConnectMuted, fontSize = 12.sp, lineHeight = 18.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        }
    }
}

@Composable
private fun FocusButton(label: String, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(
        Modifier.width(180.dp).height(48.dp).clip(RoundedCornerShape(14.dp))
            .background(if (focused) Color(0xFF241018) else ConnectPanel)
            .border(1.dp, if (focused) ConnectRed else Color(0xFF303A48), RoundedCornerShape(14.dp))
            .onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() },
        contentAlignment = Alignment.Center
    ) { Text(label, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black) }
}
