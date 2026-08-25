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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * New XSportsX mark. This is a fresh implementation; it does not reuse the
 * previous XtremeLogo geometry or rendering code.
 */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val transition = rememberInfiniteTransition(label = "neon-x")
    val rotation by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(18000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "neon-x-rotation"
    )
    val glow by transition.animateFloat(
        initialValue = 0.72f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "neon-x-glow"
    )

    Box(modifier.size(size)) {
        Canvas(Modifier.size(size).rotate(rotation)) {
            val w = this.size.width
            val h = this.size.height
            val pad = w * 0.16f
            val left = pad
            val right = w - pad
            val top = pad
            val bottom = h - pad
            val midX = w * 0.5f
            val midY = h * 0.5f

            val red = Color(0xFFFF1744)
            val blue = Color(0xFF2196FF)
            val white = Color.White

            // Four separate tapered chevrons make the new X silhouette.
            val redTop = Path().apply {
                moveTo(left, top)
                lineTo(midX - w * 0.035f, midY - h * 0.035f)
                lineTo(midX - w * 0.115f, midY - h * 0.115f)
                lineTo(left + w * 0.085f, top + h * 0.085f)
                close()
            }
            val redBottom = Path().apply {
                moveTo(left, bottom)
                lineTo(midX - w * 0.035f, midY + h * 0.035f)
                lineTo(midX - w * 0.115f, midY + h * 0.115f)
                lineTo(left + w * 0.085f, bottom - h * 0.085f)
                close()
            }
            val blueTop = Path().apply {
                moveTo(right, top)
                lineTo(midX + w * 0.035f, midY - h * 0.035f)
                lineTo(midX + w * 0.115f, midY - h * 0.115f)
                lineTo(right - w * 0.085f, top + h * 0.085f)
                close()
            }
            val blueBottom = Path().apply {
                moveTo(right, bottom)
                lineTo(midX + w * 0.035f, midY + h * 0.035f)
                lineTo(midX + w * 0.115f, midY + h * 0.115f)
                lineTo(right - w * 0.085f, bottom - h * 0.085f)
                close()
            }

            // Soft independent aura around each arm.
            drawNeonArm(red, left, top, midX, midY, glow, w)
            drawNeonArm(red, left, bottom, midX, midY, glow, w)
            drawNeonArm(blue, right, top, midX, midY, glow, w)
            drawNeonArm(blue, right, bottom, midX, midY, glow, w)

            drawPath(redTop, Brush.linearGradient(listOf(red, Color(0xFFFF4D6D))))
            drawPath(redBottom, Brush.linearGradient(listOf(red, Color(0xFFFF4D6D))))
            drawPath(blueTop, Brush.linearGradient(listOf(blue, Color(0xFF64B5FF))))
            drawPath(blueBottom, Brush.linearGradient(listOf(blue, Color(0xFF64B5FF))))

            // Bright center lock and two white highlights make the mark read cleanly at TV distance.
            drawCircle(white.copy(alpha = 0.94f), radius = w * 0.045f, center = Offset(midX, midY))
            drawLine(white.copy(alpha = 0.9f), Offset(left + w * 0.07f, top + h * 0.07f), Offset(midX - w * 0.06f, midY - h * 0.06f), w * 0.018f, StrokeCap.Round)
            drawLine(white.copy(alpha = 0.9f), Offset(right - w * 0.07f, bottom - h * 0.07f), Offset(midX + w * 0.06f, midY + h * 0.06f), w * 0.018f, StrokeCap.Round)
        }
    }
}

private fun DrawScope.drawNeonArm(
    color: Color,
    startX: Float,
    startY: Float,
    endX: Float,
    endY: Float,
    intensity: Float,
    width: Float
) {
    val aura = color.copy(alpha = 0.18f * intensity)
    drawLine(aura, Offset(startX, startY), Offset(endX, endY), width * 0.28f, StrokeCap.Round)
    drawLine(color.copy(alpha = 0.28f * intensity), Offset(startX, startY), Offset(endX, endY), width * 0.16f, StrokeCap.Round)
}
