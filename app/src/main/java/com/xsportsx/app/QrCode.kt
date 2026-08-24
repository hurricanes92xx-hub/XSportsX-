package com.xsportsx.app

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.foundation.Image
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.MultiFormatWriter
import com.google.zxing.common.BitMatrix

fun makeQrBitmap(payload: String, size: Int = 760): Bitmap {
    val matrix: BitMatrix = MultiFormatWriter().encode(payload, BarcodeFormat.QR_CODE, size, size)
    val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
    for (x in 0 until size) for (y in 0 until size) bitmap.setPixel(x, y, if (matrix[x, y]) Color.BLACK else Color.WHITE)
    return bitmap
}

@Composable
fun QrImage(payload: String, modifier: Modifier = Modifier) {
    Image(bitmap = makeQrBitmap(payload).asImageBitmap(), contentDescription = "XSportsX pairing QR code", modifier = modifier)
}
