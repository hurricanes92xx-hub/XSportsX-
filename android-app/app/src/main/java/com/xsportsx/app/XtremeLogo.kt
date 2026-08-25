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
 * Animated neon X based on the supplied XSportsX artwork.
 * Red/white energy dominates the left side, blue/white energy the right,
 * with a soft stadium-style glow and slow continuous rotation.
 */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val transition = rememberInfiniteTransition(label = "xsportsx-neon-x")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 18000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "xsportsx-neon-x-rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.62f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "xsportsx-neon-x-pulse"
    )

    Box(
        modifier = modifier
            .size(size)
            .background(
                Brush.radialGradient(
                    listOf(
                        Color(0x5532B7FF).copy(alpha = pulse),
                        Color(0x44FF1744).copy(alpha = pulse),
                        Color(0x00000000)
                    )
                ),
                CircleShape
            )
    ) {
        Box(Modifier.size(size).rotate(rotation)) {
            Canvas(Modifier.size(size)) {
                val d = min(this.size.width, this.size.height)
                val p = d * 0.14f
                val left = p
                val right = d - p
                val top = p
                val bottom = d - p
                val cx = d / 2f
                val cy = d / 2f
                val red = Color(0xFFFF244D)
                val blue = Color(0xFF36B9FF)
                val white = Color.White
                val core = d * 0.105f
                val glowWide = core * 5.5f
                val glowMid = core * 2.8f
                val glowAlpha = 0.42f * pulse

                // Broad red/blue neon bloom.
                drawLine(red.copy(alpha = glowAlpha), Offset(left, top), Offset(cx, cy), glowWide, StrokeCap.Round)
                drawLine(red.copy(alpha = glowAlpha), Offset(cx, cy), Offset(right, bottom), glowWide, StrokeCap.Round)
                drawLine(blue.copy(alpha = glowAlpha), Offset(right, top), Offset(cx, cy), glowWide, StrokeCap.Round)
                drawLine(blue.copy(alpha = glowAlpha), Offset(cx, cy), Offset(left, bottom), glowWide, StrokeCap.Round)

                // Tighter colored glow.
                drawLine(red.copy(alpha = 0.72f * pulse), Offset(left, top), Offset(cx, cy), glowMid, StrokeCap.Round)
                drawLine(red.copy(alpha = 0.72f * pulse), Offset(cx, cy), Offset(right, bottom), glowMid, StrokeCap.Round)
                drawLine(blue.copy(alpha = 0.72f * pulse), Offset(right, top), Offset(cx, cy), glowMid, StrokeCap.Round)
                drawLine(blue.copy(alpha = 0.72f * pulse), Offset(cx, cy), Offset(left, bottom), glowMid, StrokeCap.Round)

                // Crisp neon X.
                drawLine(red, Offset(left, top), Offset(cx, cy), core, StrokeCap.Round)
                drawLine(red, Offset(cx, cy), Offset(right, bottom), core, StrokeCap.Round)
                drawLine(blue, Offset(right, top), Offset(cx, cy), core, StrokeCap.Round)
                drawLine(blue, Offset(cx, cy), Offset(left, bottom), core, StrokeCap.Round)

                // Hot white center highlights, matching the supplied artwork.
                val highlight = core * 0.24f
                drawLine(white.copy(alpha = 0.95f), Offset(left, top), Offset(cx, cy), highlight, StrokeCap.Round)
                drawLine(white.copy(alpha = 0.95f), Offset(right, top), Offset(cx, cy), highlight, StrokeCap.Round)
                drawLine(white.copy(alpha = 0.86f), Offset(cx, cy), Offset(right, bottom), highlight, StrokeCap.Round)
                drawLine(white.copy(alpha = 0.86f), Offset(cx, cy), Offset(left, bottom), highlight, StrokeCap.Round)
            }
        }
    }
}
