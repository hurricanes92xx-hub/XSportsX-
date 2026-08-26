package com.xsportsx.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.zxing.BarcodeFormat
import com.google.zxing.MultiFormatWriter
import java.util.UUID

@Composable
fun PairingQrCard(modifier: Modifier = Modifier) {
    val pairingCode = remember { UUID.randomUUID().toString().replace("-", "").take(12).uppercase() }
    val payload = "${BuildConfig.PAIRING_BASE_URL}/pair?code=$pairingCode"

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(22.dp))
            .background(Color(0xFF101720))
            .padding(18.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        PairingQrCode(payload, 150.dp)
        Spacer(Modifier.width(20.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("PAIR YOUR DEVICE", color = Color(0xFFFF1744), fontSize = 12.sp)
            Text("Scan this QR code", color = Color.White, fontSize = 20.sp)
            Text("Use your phone to pair with this XSportsX TV/device.", color = Color(0xFF8D94A2), fontSize = 12.sp)
            Text("PAIR CODE  $pairingCode", color = Color(0xFF2196FF), fontSize = 11.sp)
        }
    }
}

@Composable
private fun PairingQrCode(value: String, size: Dp) {
    val matrix = remember(value) {
        MultiFormatWriter().encode(value, BarcodeFormat.QR_CODE, 256, 256)
    }
    Canvas(
        Modifier
            .size(size)
            .clip(RoundedCornerShape(12.dp))
            .background(Color.White)
            .padding(8.dp)
    ) {
        val moduleW = this.size.width / matrix.width
        val moduleH = this.size.height / matrix.height
        for (x in 0 until matrix.width) {
            for (y in 0 until matrix.height) {
                if (matrix[x, y]) {
                    drawRect(
                        Color.Black,
                        topLeft = androidx.compose.ui.geometry.Offset(x * moduleW, y * moduleH),
                        size = androidx.compose.ui.geometry.Size(moduleW + 0.5f, moduleH + 0.5f)
                    )
                }
            }
        }
    }
}
