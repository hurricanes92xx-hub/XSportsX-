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

/** Aggressive XSportsX mark: thicker, jagged, fractured and red-hot. */
@Composable
fun XtremeLogo(modifier: Modifier = Modifier, size: Dp = 58.dp) {
    val motion = rememberInfiniteTransition(label = "xsportsx-main-logo")
    val rotation by motion.animateFloat(0f, 360f, infiniteRepeatable(tween(24000, easing = LinearEasing)), label = "xsportsx-logo-rotation")
    val pulse by motion.animateFloat(.72f, 1f, infiniteRepeatable(tween(700, easing = LinearEasing), repeatMode = RepeatMode.Reverse), label = "xsportsx-logo-pulse")
    Box(modifier.size(size)) {
        Canvas(Modifier.size(size).rotate(rotation)) {
            val w = this.size.width; val h = this.size.height; val cx = w / 2f; val cy = h / 2f
            val red = Color(0xFFFF102F); val redHot = Color(0xFFFF435C); val redDeep = Color(0xFF9D001D)
            val blue = Color(0xFF168CFF); val blueHot = Color(0xFF72C8FF); val white = Color.White; val core = Color(0xFF030509)
            val xPath = Path().apply {
                moveTo(w*.045f,h*.08f); lineTo(w*.29f,h*.08f); lineTo(w*.43f,h*.27f); lineTo(w*.50f,h*.38f)
                lineTo(w*.57f,h*.27f); lineTo(w*.71f,h*.08f); lineTo(w*.955f,h*.08f); lineTo(w*.70f,cy)
                lineTo(w*.955f,h*.92f); lineTo(w*.70f,h*.92f); lineTo(w*.57f,h*.73f); lineTo(w*.50f,h*.62f)
                lineTo(w*.43f,h*.73f); lineTo(w*.29f,h*.92f); lineTo(w*.045f,h*.92f); lineTo(w*.30f,cy); close()
            }
            drawPath(xPath, core)
            drawPath(xPath, Brush.linearGradient(listOf(redDeep.copy(alpha=.85f*pulse), red.copy(alpha=.72f*pulse), white.copy(alpha=.20f), blue.copy(alpha=.72f*pulse), blueHot.copy(alpha=.75f*pulse))), style = androidx.compose.ui.graphics.drawscope.Stroke(w*.19f, cap=StrokeCap.Butt, join=StrokeJoin.Miter))
            drawPath(xPath, Brush.linearGradient(listOf(red, redHot, white, blueHot, blue)), style = androidx.compose.ui.graphics.drawscope.Stroke(w*.085f, cap=StrokeCap.Butt, join=StrokeJoin.Miter))
            drawPath(xPath, Brush.linearGradient(listOf(white.copy(alpha=.95f), redHot, white, blueHot, white.copy(alpha=.95f))), style = androidx.compose.ui.graphics.drawscope.Stroke(w*.026f, cap=StrokeCap.Butt, join=StrokeJoin.Miter))
            val cut = white.copy(alpha=.82f)
            drawLine(cut, Offset(w*.12f,h*.17f), Offset(w*.32f,h*.34f), w*.014f, StrokeCap.Butt)
            drawLine(cut, Offset(w*.88f,h*.83f), Offset(w*.68f,h*.66f), w*.014f, StrokeCap.Butt)
            drawLine(redHot.copy(alpha=.9f), Offset(w*.18f,h*.48f), Offset(w*.36f,h*.42f), w*.010f, StrokeCap.Butt)
            drawLine(blueHot.copy(alpha=.9f), Offset(w*.82f,h*.52f), Offset(w*.64f,h*.58f), w*.010f, StrokeCap.Butt)
            drawCircle(white.copy(alpha=.34f*pulse), w*.13f, Offset(cx,cy))
            drawCircle(white, w*.032f, Offset(cx,cy))
            val shard = .60f * pulse
            val shards = listOf(
                Triple(red, Offset(w*.02f,h*.23f), Offset(w*.16f,h*.28f)), Triple(red, Offset(w*.04f,h*.78f), Offset(w*.18f,h*.71f)),
                Triple(redHot, Offset(w*.18f,h*.03f), Offset(w*.23f,h*.12f)), Triple(redHot, Offset(w*.18f,h*.97f), Offset(w*.25f,h*.87f)),
                Triple(blue, Offset(w*.98f,h*.23f), Offset(w*.84f,h*.28f)), Triple(blue, Offset(w*.96f,h*.78f), Offset(w*.82f,h*.71f)),
                Triple(blueHot, Offset(w*.82f,h*.03f), Offset(w*.77f,h*.12f)), Triple(blueHot, Offset(w*.82f,h*.97f), Offset(w*.75f,h*.87f))
            )
            shards.forEach { (c,a,b) -> drawLine(c.copy(alpha=shard), a, b, w*.018f, StrokeCap.Butt) }
        }
    }
}
