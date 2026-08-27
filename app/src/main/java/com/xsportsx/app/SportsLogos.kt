package com.xsportsx.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas as AndroidCanvas
import androidx.compose.foundation.Canvas
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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.caverock.androidsvg.SVG
import kotlin.math.roundToInt

private data class BrandSpec(val bg: Color, val fg: Color, val accent: Color, val asset: String? = null, val mark: String)

private fun spec(key: String): BrandSpec = when (key) {
    "NFL" -> BrandSpec(Color(0xFF013369), Color.White, Color(0xFFD50A0A), "nfl", "NFL")
    "NBA" -> BrandSpec(Color(0xFF17408B), Color.White, Color(0xFFE31837), "nba", "NBA")
    "NCAA FB", "NCAA BB", "NCAA VB" -> BrandSpec(Color(0xFF102B55), Color.White, Color(0xFFFFC72C), "ncaa", "NCAA")
    "MLB" -> BrandSpec(Color(0xFF041E42), Color.White, Color(0xFFE31837), "mlb", "MLB")
    "NHL" -> BrandSpec(Color(0xFF111820), Color.White, Color(0xFFB8C7D9), "nhl", "NHL")
    "UFC" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFD20A0A), "ufc", "UFC")
    "WRESTLING", "WWE" -> BrandSpec(Color(0xFF090909), Color.White, Color(0xFFE31B23), "wwe", "WWE")
    "AEW" -> BrandSpec(Color(0xFF101010), Color.White, Color(0xFFFFFFFF), "aew", "AEW")
    "TNA" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE61B1F), "tna", "TNA")
    "BOXING" -> BrandSpec(Color(0xFF171717), Color.White, Color(0xFFE53935), null, "BOXING")
    "RUGBY" -> BrandSpec(Color(0xFF063B2B), Color.White, Color(0xFF49D17D), null, "RUGBY")
    "VOLLEYBALL" -> BrandSpec(Color(0xFF073A66), Color.White, Color(0xFFF7B500), null, "VB")
    "LACROSSE" -> BrandSpec(Color(0xFF102A43), Color.White, Color(0xFF55B6FF), null, "LAX")
    "FORMULA 1" -> BrandSpec(Color(0xFF050505), Color.White, Color(0xFFE10600), null, "F1")
    "NASCAR" -> BrandSpec(Color(0xFF0A0A0A), Color.White, Color(0xFF1E8BFF), null, "NASCAR")
    "DTM" -> BrandSpec(Color(0xFF101010), Color.White, Color(0xFFEC1C24), null, "DTM")
    "MOTOGP" -> BrandSpec(Color(0xFF050505), Color.White, Color(0xFFE10600), null, "MotoGP")
    "WRC" -> BrandSpec(Color(0xFF0A0A0A), Color.White, Color(0xFF2E73FF), null, "WRC")
    "WEC" -> BrandSpec(Color(0xFF071A35), Color.White, Color(0xFF3BB8FF), null, "WEC")
    "FORMULA E" -> BrandSpec(Color(0xFF061B2A), Color.White, Color(0xFF20E0D0), null, "FE")
    "MXGP" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE30613), null, "MXGP")
    "MONSTER JAM" -> BrandSpec(Color(0xFF080808), Color.White, Color(0xFFE31B23), null, "MONSTER JAM")
    "SOCCER" -> BrandSpec(Color(0xFF0C2C45), Color.White, Color(0xFF5ED0FF), null, "SOCCER")
    "MLS" -> BrandSpec(Color(0xFF071A35), Color.White, Color(0xFF9CC7FF), null, "MLS")
    "EPL" -> BrandSpec(Color(0xFF38003C), Color.White, Color(0xFF00FF85), "premierleague", "EPL")
    "WNBA" -> BrandSpec(Color(0xFF24134F), Color.White, Color(0xFFFF4B6E), null, "WNBA")
    else -> BrandSpec(Color(0xFF151A22), Color.White, Color(0xFFFF1838), null, key.take(10))
}

private fun networkSpec(key: String): BrandSpec = when (key) {
    "ESPN", "ESPN2", "ESPNU", "ESPN+" -> BrandSpec(Color(0xFF090909), Color.White, Color(0xFFE31837), "espn", key)
    "CBS SPORTS", "CBS" -> BrandSpec(Color(0xFF101A28), Color.White, Color(0xFF4AA3FF), "cbs", "CBS SPORTS")
    "NFL NETWORK" -> BrandSpec(Color(0xFF013369), Color.White, Color(0xFFD50A0A), "nfl", "NFL NETWORK")
    "NBA TV" -> BrandSpec(Color(0xFF17408B), Color.White, Color(0xFFE31837), "nba", "NBA TV")
    "MLB NETWORK" -> BrandSpec(Color(0xFF041E42), Color.White, Color(0xFFE31837), "mlb", "MLB NETWORK")
    "NHL NETWORK" -> BrandSpec(Color(0xFF111820), Color.White, Color(0xFFB8C7D9), "nhl", "NHL NETWORK")
    "UFC FIGHT PASS" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFD20A0A), "ufc", "FIGHT PASS")
    "WWE" -> BrandSpec(Color(0xFF090909), Color.White, Color(0xFFE31B23), "wwe", "WWE")
    "AEW" -> BrandSpec(Color(0xFF101010), Color.White, Color.White, "aew", "AEW")
    "TNA" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE61B1F), "tna", "TNA")
    "FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), null, "FS1")
    "SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), null, "SEC")
    "ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), null, "ACC")
    "BIG TEN NETWORK" -> BrandSpec(Color(0xFF082B55), Color.White, Color(0xFF7CC8FF), null, "B1G")
    "PAC-12 NETWORK" -> BrandSpec(Color(0xFF10233F), Color.White, Color(0xFF00A6CE), null, "PAC-12")
    "RED BULL TV" -> BrandSpec(Color(0xFF071A3A), Color.White, Color(0xFFE31B23), "redbull", "RED BULL")
    "MONSTER JAM" -> BrandSpec(Color(0xFF080808), Color.White, Color(0xFFE31B23), null, "MONSTER JAM")
    "RUGBYPASS TV" -> BrandSpec(Color(0xFF073B2A), Color.White, Color(0xFF49D17D), null, "RUGBYPASS")
    else -> BrandSpec(Color(0xFF151A22), Color.White, Color(0xFFFF1838), null, key.take(10))
}

private fun loadSvgBitmap(context: Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val bitmap = Bitmap.createBitmap(width.coerceAtLeast(1), height.coerceAtLeast(1), Bitmap.Config.ARGB_8888)
    val canvas = AndroidCanvas(bitmap)
    val svg = SVG.getFromAsset(context.assets, "brand_logos/$asset.svg")
    svg.renderToCanvas(canvas)
    bitmap
}.getOrNull()

@Composable
private fun LocalSvgLogo(asset: String, modifier: Modifier, size: Dp, description: String) {
    val context = LocalContext.current
    val px = with(LocalDensity.current) { size.toPx().roundToInt().coerceAtLeast(1) }
    val bitmap = remember(asset, px) { loadSvgBitmap(context, asset, px, px) }
    if (bitmap != null) Image(bitmap = bitmap.asImageBitmap(), contentDescription = description, modifier = modifier.size(size), contentScale = ContentScale.Fit)
}

@Composable
private fun VectorBrandMark(spec: BrandSpec, size: Dp) {
    Box(Modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val w = size.toPx(); val h = size.toPx(); val c = center
            when (spec.mark) {
                "F1" -> { drawLine(spec.accent, Offset(w*.18f,h*.30f), Offset(w*.82f,h*.30f), 8f); drawLine(spec.accent,Offset(w*.18f,h*.30f),Offset(w*.18f,h*.70f),8f); drawLine(spec.accent,Offset(w*.18f,h*.50f),Offset(w*.65f,h*.50f),7f); drawLine(Color.White,Offset(w*.64f,h*.30f),Offset(w*.82f,h*.70f),7f) }
                "NASCAR" -> { val colors=listOf(Color(0xFFFFC400),Color(0xFFFF6A00),Color(0xFFE31B23),Color(0xFF6B6B6B),Color.White); colors.forEachIndexed{i,col->drawLine(col,Offset(w*.18f+i*8,h*.25f),Offset(w*.42f+i*8,h*.75f),7f)} }
                "DTM" -> { drawRect(spec.accent,Offset(w*.16f,h*.28f),Size(w*.27f,h*.44f)); drawRect(Color.White,Offset(w*.43f,h*.28f),Size(w*.15f,h*.44f)); drawRect(Color(0xFF1E6CFF),Offset(w*.58f,h*.28f),Size(w*.26f,h*.44f)) }
                "WRC" -> { drawLine(spec.accent,Offset(w*.18f,h*.35f),Offset(w*.82f,h*.35f),6f); drawLine(Color.White,Offset(w*.22f,h*.55f),Offset(w*.78f,h*.55f),5f); drawLine(spec.accent,Offset(w*.30f,h*.75f),Offset(w*.70f,h*.75f),4f) }
                "WEC" -> { drawCircle(spec.accent,radius=w*.30f,center=c,style=Stroke(width=6f)); drawLine(Color.White,Offset(w*.28f,h*.50f),Offset(w*.72f,h*.50f),6f) }
                "FE" -> { drawLine(spec.accent,Offset(w*.20f,h*.68f),Offset(w*.80f,h*.32f),9f); drawLine(Color.White,Offset(w*.30f,h*.70f),Offset(w*.65f,h*.30f),4f) }
                "SOCCER" -> { drawCircle(Color.White,radius=w*.28f,center=c); drawCircle(spec.bg,radius=w*.10f,center=c) }
                "SEC" -> { drawCircle(spec.accent,radius=w*.28f,center=c); drawCircle(spec.bg,radius=w*.20f,center=c,style=Stroke(width=5f)) }
                "ACC" -> { drawLine(spec.accent,Offset(w*.18f,h*.72f),Offset(w*.82f,h*.28f),9f); drawLine(Color.White,Offset(w*.18f,h*.50f),Offset(w*.58f,h*.50f),6f) }
                "B1G" -> { drawRoundRect(color=spec.accent, topLeft=Offset(w*.14f,h*.28f), size=Size(w*.72f,h*.44f), cornerRadius=CornerRadius(8f,8f), style=Stroke(width=6f)) }
                "PAC-12" -> { drawLine(spec.accent,Offset(w*.20f,h*.68f),Offset(w*.50f,h*.30f),7f); drawLine(Color.White,Offset(w*.50f,h*.30f),Offset(w*.80f,h*.68f),7f) }
                "FS1" -> { drawOval(Color.White,Offset(w*.13f,h*.27f),Size(w*.74f,h*.46f),style=Stroke(width=5f)) }
                else -> { drawCircle(spec.accent,radius=w*.30f,center=c); drawCircle(spec.bg,radius=w*.21f,center=c,style=Stroke(width=5f)) }
            }
        }
        Text(spec.mark, color=spec.fg, fontSize=if(spec.mark.length>6) 7.sp else 14.sp, fontWeight=FontWeight.Black, textAlign=TextAlign.Center, maxLines=1)
    }
}

@Composable
private fun BrandBox(spec: BrandSpec, size: Dp, description: String) {
    Box(Modifier.size(size).clip(RoundedCornerShape(size/3)).background(spec.bg).border(1.dp,spec.accent.copy(alpha=.9f),RoundedCornerShape(size/3)),contentAlignment=Alignment.Center) {
        if (spec.asset != null) LocalSvgLogo(spec.asset,Modifier,size*.78f,description) else VectorBrandMark(spec,size*.78f)
    }
}

@Composable
fun XSportsLeagueLogo(name: String, modifier: Modifier = Modifier, size: Dp = 72.dp) {
    val key=name.uppercase()
    Box(modifier,contentAlignment=Alignment.Center){BrandBox(spec(key),size,name)}
}

@Composable
fun XSportsNetworkLogo(name: String, modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val key=name.uppercase()
    val s=networkSpec(key)
    Box(modifier,contentAlignment=Alignment.Center){BrandBox(s,size,name);if(key=="ESPN2"||key=="ESPNU"||key=="ESPN+"){Text(key.removePrefix("ESPN"),color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Black,modifier=Modifier.align(Alignment.BottomEnd).background(Color(0xFF090909)).padding(horizontal=2.dp,vertical=1.dp))}}
}