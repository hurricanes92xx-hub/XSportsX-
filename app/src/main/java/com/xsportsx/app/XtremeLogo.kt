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

/** Exact in-app neon X mark: red left arms, blue right arms, white hot edge.
 *  The mark glows, pulses and rotates continuously on Mobile and Android TV.
 */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val transition = rememberInfiniteTransition(label = "xtreme-logo")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(24000, easing = LinearEasing), RepeatMode.Restart),
        label = "xtreme-logo-rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.68f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1600, easing = LinearEasing), RepeatMode.Reverse),
        label = "xtreme-logo-pulse"
    )

    Box(
        modifier = modifier.size(size).background(
            brush = Brush.radialGradient(
                colors = listOf(
                    Color(0x552EB7FF).copy(alpha = pulse),
                    Color(0x44FF1744).copy(alpha = pulse),
                    Color.Transparent
                )
            ),
            shape = CircleShape
        )
    ) {
        Box(Modifier.size(size).rotate(rotation)) {
            Canvas(Modifier.size(size)) {
                val d = min(this.size.width, this.size.height)
                val inset = d * 0.12f
                val left = inset
                val right = d - inset
                val top = inset
                val bottom = d - inset
                val cx = d / 2f
                val cy = d / 2f
                val red = Color(0xFFFF1838)
                val blue = Color(0xFF20A9FF)
                val white = Color.White.copy(alpha = 0.96f)
                val stroke = d * 0.145f

                // Broad neon aura.
                drawLine(Color(0x99FF1838).copy(alpha = pulse), Offset(left, top), Offset(cx, cy), stroke * 4.6f, StrokeCap.Round)
                drawLine(Color(0x99FF1838).copy(alpha = pulse), Offset(cx, cy), Offset(left, bottom), stroke * 4.6f, StrokeCap.Round)
                drawLine(Color(0x9920A9FF).copy(alpha = pulse), Offset(right, top), Offset(cx, cy), stroke * 4.6f, StrokeCap.Round)
                drawLine(Color(0x9920A9FF).copy(alpha = pulse), Offset(cx, cy), Offset(right, bottom), stroke * 4.6f, StrokeCap.Round)

                // Main angular X.
                drawLine(red, Offset(left, top), Offset(cx, cy), stroke, StrokeCap.Square)
                drawLine(red, Offset(cx, cy), Offset(left, bottom), stroke, StrokeCap.Square)
                drawLine(blue, Offset(right, top), Offset(cx, cy), stroke, StrokeCap.Square)
                drawLine(blue, Offset(cx, cy), Offset(right, bottom), stroke, StrokeCap.Square)

                // White-hot inner edge.
                drawLine(white, Offset(left + d * .01f, top), Offset(cx, cy), stroke * .19f, StrokeCap.Square)
                drawLine(white, Offset(right - d * .01f, bottom), Offset(cx, cy), stroke * .19f, StrokeCap.Square)
            }
        }
    }
}
