package com.xsportsx.app

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.min

/**
 * Prominent Xtreme neon X used in the mobile and Android TV headers.
 * The mark slowly rotates while its red/blue glow breathes so it is
 * visibly branded without distracting from the sports UI.
 */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val transition = rememberInfiniteTransition(label = "xtreme-logo")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 24000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "xtreme-logo-rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.72f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "xtreme-logo-pulse"
    )

    Box(
        modifier = modifier
            .size(size)
            .background(
                Brush.radialGradient(
                    listOf(
                        Color(0x332EB7FF).copy(alpha = pulse),
                        Color(0x22FF1744).copy(alpha = pulse),
                        Color.Transparent
                    )
                ),
                CircleShape
            )
    ) {
        Box(Modifier.size(size).rotate(rotation)) {
            Canvas(Modifier.size(size)) {
                val dimension = min(this.size.width, this.size.height)
                val inset = dimension * 0.15f
                val left = inset
                val right = dimension - inset
                val top = inset
                val bottom = dimension - inset
                val center = dimension / 2f
                val red = Color(0xFFFF1744)
                val blue = Color(0xFF32B7FF)
                val redGlow = Color(0x66FF1744).copy(alpha = pulse)
                val blueGlow = Color(0x6632B7FF).copy(alpha = pulse)
                val stroke = dimension * 0.115f

                drawLine(redGlow, Offset(left, top), Offset(center, center), strokeWidth = stroke * 4.8f, cap = StrokeCap.Round)
                drawLine(redGlow, Offset(center, center), Offset(left, bottom), strokeWidth = stroke * 4.8f, cap = StrokeCap.Round)
                drawLine(blueGlow, Offset(right, top), Offset(center, center), strokeWidth = stroke * 4.8f, cap = StrokeCap.Round)
                drawLine(blueGlow, Offset(center, center), Offset(right, bottom), strokeWidth = stroke * 4.8f, cap = StrokeCap.Round)

                drawLine(red, Offset(left, top), Offset(center, center), strokeWidth = stroke, cap = StrokeCap.Round)
                drawLine(red, Offset(center, center), Offset(left, bottom), strokeWidth = stroke, cap = StrokeCap.Round)
                drawLine(blue, Offset(right, top), Offset(center, center), strokeWidth = stroke, cap = StrokeCap.Round)
                drawLine(blue, Offset(center, center), Offset(right, bottom), strokeWidth = stroke, cap = StrokeCap.Round)

                drawLine(Color.White.copy(alpha = 0.92f), Offset(left, top), Offset(center, center), strokeWidth = stroke * 0.20f, cap = StrokeCap.Round)
                drawLine(Color.White.copy(alpha = 0.92f), Offset(right, bottom), Offset(center, center), strokeWidth = stroke * 0.20f, cap = StrokeCap.Round)
            }
        }
    }
}
