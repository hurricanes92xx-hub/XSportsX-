package com.xsportsx.app

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.min

/** Xtreme neon X logo used consistently on phone and Android TV builds. */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val transition = rememberInfiniteTransition(label = "xtreme-logo-spin")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 24000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "xtreme-logo-rotation"
    )

    Box(modifier = modifier.size(size).rotate(rotation)) {
        Canvas(Modifier.size(size)) {
            val dimension = min(this.size.width, this.size.height)
            val inset = dimension * 0.17f
            val left = inset
            val right = dimension - inset
            val top = inset
            val bottom = dimension - inset
            val center = dimension / 2f
            val red = Color(0xFFFF1744)
            val blue = Color(0xFF32B7FF)
            val redGlow = Color(0x55FF1744)
            val blueGlow = Color(0x5532B7FF)
            val stroke = dimension * 0.105f

            drawLine(redGlow, Offset(left, top), Offset(center, center), strokeWidth = stroke * 3.8f, cap = StrokeCap.Round)
            drawLine(redGlow, Offset(center, center), Offset(left, bottom), strokeWidth = stroke * 3.8f, cap = StrokeCap.Round)
            drawLine(blueGlow, Offset(right, top), Offset(center, center), strokeWidth = stroke * 3.8f, cap = StrokeCap.Round)
            drawLine(blueGlow, Offset(center, center), Offset(right, bottom), strokeWidth = stroke * 3.8f, cap = StrokeCap.Round)

            drawLine(red, Offset(left, top), Offset(center, center), strokeWidth = stroke, cap = StrokeCap.Round)
            drawLine(red, Offset(center, center), Offset(left, bottom), strokeWidth = stroke, cap = StrokeCap.Round)
            drawLine(blue, Offset(right, top), Offset(center, center), strokeWidth = stroke, cap = StrokeCap.Round)
            drawLine(blue, Offset(center, center), Offset(right, bottom), strokeWidth = stroke, cap = StrokeCap.Round)

            drawLine(Color.White.copy(alpha = 0.88f), Offset(left, top), Offset(center, center), strokeWidth = stroke * 0.22f, cap = StrokeCap.Round)
            drawLine(Color.White.copy(alpha = 0.88f), Offset(right, bottom), Offset(center, center), strokeWidth = stroke * 0.22f, cap = StrokeCap.Round)
        }
    }
}
