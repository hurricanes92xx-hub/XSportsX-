package com.xsportsx.app

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.RectF
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.caverock.androidsvg.SVG

private data class LogoPalette(val bg: Color, val fg: Color, val accent: Color)

private fun palette(key: String): LogoPalette = when {
    key.contains("NFL") -> LogoPalette(Color(0xFF013369), Color.White, Color(0xFFD50A0A))
    key == "NBA" -> LogoPalette(Color(0xFF17408B), Color.White, Color(0xFFE31837))
    key.contains("NCAA") -> LogoPalette(Color(0xFF0B2D5C), Color.White, Color(0xFF8FB9E8))
    key == "MLB" -> LogoPalette(Color(0xFF041E42), Color.White, Color(0xFFE31837))
    key == "NHL" -> LogoPalette(Color(0xFF10151D), Color.White, Color(0xFFB8C7D9))
    key.contains("UFC") -> LogoPalette(Color(0xFF151515), Color.White, Color(0xFFD20A0A))
    key.contains("BOX") -> LogoPalette(Color(0xFF24130C), Color.White, Color(0xFFFF6D00))
    key.contains("RUGBY") -> LogoPalette(Color(0xFF0B5E45), Color.White, Color(0xFF7BE0B6))
    else -> LogoPalette(Color(0xFF202A38), Color.White, Color(0xFFFF1838))
}

private fun leagueAsset(key: String): String? = when {
    key == "NFL" -> "nfl"
    key == "NBA" -> "nba"
    key == "MLB" -> "mlb"
    key == "NHL" -> "nhl"
    key == "UFC" -> "ufc"
    key.startsWith("NCAA") -> "ncaa"
    else -> null
}

private fun networkAsset(key: String): String? = when {
    key == "ESPN" || key == "ESPN2" || key == "ESPNU" || key == "ESPN+" -> "espn"
    key == "CBS SPORTS" || key == "CBS" -> "cbs"
    key == "NFL NETWORK" -> "nfl"
    key == "NBA TV" -> "nba"
    key == "MLB NETWORK" -> "mlb"
    key == "NHL NETWORK" -> "nhl"
    key == "UFC FIGHT PASS" -> "ufc"
    else -> null
}

private fun loadSvgBitmap(context: android.content.Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val bitmap = Bitmap.createBitmap(width.coerceAtLeast(1), height.coerceAtLeast(1), Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    val svg = SVG.getFromAsset(context.assets, "brand_logos/$asset.svg")
    svg.renderToCanvas(canvas, RectF(0f, 0f, width.toFloat(), height.toFloat()))
    bitmap
}.getOrNull()

@Composable
private fun LocalSvgLogo(asset: String, modifier: Modifier, size: Dp, description: String) {
    val context = LocalContext.current
    val px = with(LocalDensity.current) { size.toPx().roundToInt().coerceAtLeast(1) }
    val bitmap = remember(asset, px) { loadSvgBitmap(context, asset, px, px) }
    if (bitmap != null) {
        Image(bitmap = bitmap.asImageBitmap(), contentDescription = description, modifier = modifier.size(size), contentScale = ContentScale.Fit)
    }
}

@Composable
fun XSportsLeagueLogo(name: String, modifier: Modifier = Modifier, size: Dp = 72.dp) {
    val key = name.uppercase()
    val asset = leagueAsset(key)
    if (asset != null) {
        val frame = Modifier.size(size).clip(RoundedCornerShape(size / 3)).background(palette(key).bg).border(1.dp, palette(key).accent.copy(alpha = .9f), RoundedCornerShape(size / 3)).then(modifier)
        Box(frame, contentAlignment = Alignment.Center) { LocalSvgLogo(asset, Modifier, size * .82f, name) }
    } else {
        val p = palette(key)
        val main = when {
            key == "FORMULA 1" -> "F1"
            key == "MOTOGP" -> "MotoGP"
            key == "FORMULA E" -> "FE"
            key == "MONSTER JAM" -> "MJ"
            else -> key.replace(" NETWORK", "").take(8)
        }
        Box(modifier.size(size).clip(RoundedCornerShape(size / 3)).background(p.bg).border(1.dp, p.accent.copy(alpha = .8f), RoundedCornerShape(size / 3)), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Text(main, color = p.fg, fontSize = if (main.length > 5) 9.sp else 15.sp, fontWeight = FontWeight.Black, maxLines = 1, textAlign = TextAlign.Center)
                Spacer(Modifier.height(2.dp)); Box(Modifier.width(size * .52f).height(2.dp).background(p.accent))
                Spacer(Modifier.height(2.dp)); Text(when (key) { "NCAA FB" -> "FOOTBALL"; "NCAA BB" -> "BASKETBALL"; "NCAA VB" -> "VOLLEYBALL"; else -> "SPORTS" }, color = p.fg.copy(alpha = .72f), fontSize = 5.sp, fontWeight = FontWeight.Bold, letterSpacing = .45.sp, maxLines = 1)
            }
        }
    }
}

@Composable
fun XSportsNetworkLogo(name: String, modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val key = name.uppercase()
    val asset = networkAsset(key)
    if (asset != null) {
        val p = palette(key)
        Box(modifier.size(size).clip(RoundedCornerShape(size / 4)).background(if (key.startsWith("ESPN")) Color(0xFF090909) else p.bg).border(1.dp, p.accent.copy(alpha = .85f), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
            Box(Modifier.fillMaxSize().padding(6.dp), contentAlignment = Alignment.Center) {
                LocalSvgLogo(asset, Modifier, if (key.startsWith("ESPN")) size * .82f else size * .72f, name)
                if (key == "ESPN2" || key == "ESPNU" || key == "ESPN+") {
                    Text(key.removePrefix("ESPN"), color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, modifier = Modifier.align(Alignment.BottomEnd).background(Color(0xFF090909)).padding(horizontal = 2.dp, vertical = 1.dp))
                }
                if (key == "CBS SPORTS") Text("SPORTS", color = Color.White, fontSize = 6.sp, fontWeight = FontWeight.Black, modifier = Modifier.align(Alignment.BottomCenter))
            }
        }
    } else {
        val p = palette(key)
        Box(modifier.size(size).clip(RoundedCornerShape(size / 4)).background(p.bg).border(1.dp, p.accent.copy(alpha = .8f), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
            Text(when { key.contains("BIG TEN") -> "B1G"; key.contains("PAC-12") -> "PAC-12"; key.contains("RED BULL") -> "RED BULL"; else -> key.take(8) }, color = p.fg, fontSize = if (key.length > 6) 7.sp else 12.sp, fontWeight = FontWeight.Black, letterSpacing = .25.sp, maxLines = 1, textAlign = TextAlign.Center)
        }
    }
}
