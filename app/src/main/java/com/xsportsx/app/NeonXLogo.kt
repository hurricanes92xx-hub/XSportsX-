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
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Premium XSportsX mark. Replaces the legacy logo completely. */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 58.dp) {
    val motion = rememberInfiniteTransition(label = "xsportsx-main-logo")
    val rotation by motion.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(24000, easing = LinearEasing)),
        label = "xsportsx-logo-rotation"
    )
    val pulse by motion.animateFloat(
        initialValue = 0.78f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            tween(900, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "xsportsx-logo-pulse"
    )

    Box(modifier.size(size)) {
        Canvas(Modifier.size(size).rotate(rotation)) {
            val w = this.size.width
            val h = this.size.height
            val cx = w / 2f
            val cy = h / 2f
            val red = Color(0xFFFF163D)
            val redHot = Color(0xFFFF5A73)
            val blue = Color(0xFF168CFF)
            val blueHot = Color(0xFF6BC4FF)
            val white = Color(0xFFFFFFFF)
            val core = Color(0xFF05080E)

            // The same aggressive silhouette as the supplied X: four angular arms,
            // red on the left, blue on the right, with a bright white-hot edge.
            val xPath = Path().apply {
                moveTo(w * .08f, h * .12f)
                lineTo(w * .30f, h * .12f)
                lineTo(cx, h * .39f)
                lineTo(w * .70f, h * .12f)
                lineTo(w * .92f, h * .12f)
                lineTo(w * .63f, cy)
                lineTo(w * .92f, h * .88f)
                lineTo(w * .70f, h * .88f)
                lineTo(cx, h * .61f)
                lineTo(w * .30f, h * .88f)
                lineTo(w * .08f, h * .88f)
                lineTo(w * .37f, cy)
                close()
            }

            // Black inset keeps the mark crisp instead of looking like four blobs.
            drawPath(xPath, core)

            // Large atmospheric glow layers.
            drawPath(
                xPath,
                brush = Brush.linearGradient(listOf(red.copy(alpha = .48f * pulse), white.copy(alpha = .16f), blue.copy(alpha = .48f * pulse))),
                style = androidx.compose.ui.graphics.drawscope.Stroke(w * .13f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            )
            drawPath(
                xPath,
                brush = Brush.linearGradient(listOf(red, white, blue)),
                style = androidx.compose.ui.graphics.drawscope.Stroke(w * .055f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            )
            drawPath(
                xPath,
                brush = Brush.linearGradient(listOf(redHot, white, blueHot)),
                style = androidx.compose.ui.graphics.drawscope.Stroke(w * .018f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            )

            // White-hot diagonal highlights on the inner faces.
            drawLine(white.copy(alpha = .95f), Offset(w * .15f, h * .19f), Offset(cx - w * .10f, cy - h * .10f), w * .012f, StrokeCap.Round)
            drawLine(white.copy(alpha = .95f), Offset(w * .85f, h * .81f), Offset(cx + w * .10f, cy + h * .10f), w * .012f, StrokeCap.Round)

            // Central energy core.
            drawCircle(white.copy(alpha = .30f * pulse), w * .105f, Offset(cx, cy))
            drawCircle(white.copy(alpha = .95f), w * .026f, Offset(cx, cy))

            // Small electric shards give the logo the high-energy sports-tech look.
            val shardAlpha = .45f * pulse
            drawLine(red.copy(alpha = shardAlpha), Offset(w * .05f, h * .27f), Offset(w * .15f, h * .31f), w * .012f, StrokeCap.Round)
            drawLine(red.copy(alpha = shardAlpha), Offset(w * .08f, h * .73f), Offset(w * .18f, h * .69f), w * .010f, StrokeCap.Round)
            drawLine(blue.copy(alpha = shardAlpha), Offset(w * .95f, h * .27f), Offset(w * .85f, h * .31f), w * .012f, StrokeCap.Round)
            drawLine(blue.copy(alpha = shardAlpha), Offset(w * .92f, h * .73f), Offset(w * .82f, h * .69f), w * .010f, StrokeCap.Round)
        }
    }
}
