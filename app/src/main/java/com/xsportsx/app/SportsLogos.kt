package com.xsportsx.app

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas as AndroidCanvas
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.produceState
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.roundToInt

private data class BrandSpec(val bg: Color,val fg: Color,val accent: Color,val asset: String? = null,val mark: String,val remote: String? = null)
private const val WIKI = "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
private const val LOGOKIT = "https://img.logokit.com/"
private fun remote(value: String) = if (value.startsWith("https://")) value else LOGOKIT + value

private fun spec(key: String): BrandSpec = when (key) {
    "NFL" -> BrandSpec(Color(0xFF013369), Color.White, Color(0xFFD50A0A), "nfl", "NFL")
    "NBA" -> BrandSpec(Color(0xFF17408B), Color.White, Color(0xFFE31837), "nba", "NBA")
    "NCAA FB", "NCAA BB", "NCAA VB" -> BrandSpec(Color(0xFF102B55), Color.White, Color(0xFFFFC72C), "ncaa", "NCAA")
    "MLB" -> BrandSpec(Color(0xFF041E42), Color.White, Color(0xFFE31837), "mlb", "MLB")
    "NHL" -> BrandSpec(Color(0xFF111820), Color.White, Color(0xFFB8C7D9), "nhl", "NHL")
    "UFC" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFD20A0A), "ufc", "UFC")
    "WRESTLING", "WWE" -> BrandSpec(Color(0xFF090909), Color.White, Color(0xFFE31B23), "wwe", "WWE")
    "AEW" -> BrandSpec(Color(0xFF101010), Color.White, Color.White, "aew", "AEW")
    "TNA" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE61B1F), "tna", "TNA")
    "BOXING" -> BrandSpec(Color(0xFF171717), Color.White, Color(0xFFE53935), null, "BOXING", remote("worldboxing.org"))
    "RUGBY" -> BrandSpec(Color(0xFF063B2B), Color.White, Color(0xFF49D17D), null, "RUGBY", remote("world.rugby"))
    "VOLLEYBALL" -> BrandSpec(Color(0xFF073A66), Color.White, Color(0xFFF7B500), null, "VB", remote("volleyballworld.com"))
    "LACROSSE" -> BrandSpec(Color(0xFF102A43), Color.White, Color(0xFF55B6FF), null, "LAX", remote("usalacrosse.com"))
    "FORMULA 1" -> BrandSpec(Color(0xFF050505), Color.White, Color(0xFFE10600), null, "F1", remote("formula1.com"))
    "NASCAR" -> BrandSpec(Color(0xFF0A0A0A), Color.White, Color(0xFF1E8BFF), null, "NASCAR", remote("nascar.com"))
    "DTM" -> BrandSpec(Color(0xFF101010), Color.White, Color(0xFFEC1C24), null, "DTM", remote("dtm.com"))
    "MOTOGP" -> BrandSpec(Color(0xFF050505), Color.White, Color(0xFFE10600), null, "MotoGP", remote(WIKI + "MotoGP_logo_(2024).svg"))
    "WRC" -> BrandSpec(Color(0xFF0A0A0A), Color.White, Color(0xFF2E73FF), null, "WRC", remote(WIKI + "WRC_(2023)_logo_official_(SGDB_111749).png"))
    "WEC" -> BrandSpec(Color(0xFF071A35), Color.White, Color(0xFF3BB8FF), null, "WEC", remote(WIKI + "WEC_Logo.svg"))
    "IMSA" -> BrandSpec(Color(0xFF0A0A0A), Color.White, Color(0xFFE31B23), null, "IMSA", remote(WIKI + "International_Motor_Sports_Association_logo_(2014-present).svg"))
    "FORMULA E" -> BrandSpec(Color(0xFF061B2A), Color.White, Color(0xFF20E0D0), null, "FE", remote(WIKI + "Formula-e-logo-championship_2023.svg"))
    "MXGP" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE30613), null, "MXGP", remote(WIKI + "Logo_MXGP.svg"))
    "MONSTER JAM" -> BrandSpec(Color(0xFF080808), Color.White, Color(0xFFE31B23), null, "MONSTER JAM", remote("monsterjam.com"))
    "SOCCER" -> BrandSpec(Color(0xFF0C2C45), Color.White, Color(0xFF5ED0FF), null, "SOCCER")
    "MLS" -> BrandSpec(Color(0xFF071A35), Color.White, Color(0xFF9CC7FF), null, "MLS", remote("mlssoccer.com"))
    "EPL" -> BrandSpec(Color(0xFF38003C), Color.White, Color(0xFF00FF85), "premierleague", "EPL")
    "WNBA" -> BrandSpec(Color(0xFF24134F), Color.White, Color(0xFFFF4B6E), null, "WNBA", remote("wnba.com"))
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
    "FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), null, "FS1", remote("foxsports.com"))
    "SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), null, "SEC", remote("secsports.com"))
    "ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), null, "ACC", remote("theacc.com"))
    "BIG TEN NETWORK" -> BrandSpec(Color(0xFF082B55), Color.White, Color(0xFF7CC8FF), null, "B1G", remote("bigten.org"))
    "PAC-12 NETWORK" -> BrandSpec(Color(0xFF10233F), Color.White, Color(0xFF00A6CE), null, "PAC-12", remote("pac-12.com"))
    "RED BULL TV" -> BrandSpec(Color(0xFF071A3A), Color.White, Color(0xFFE31B23), null, "RED BULL", remote("redbull.com"))
    "MONSTER JAM" -> BrandSpec(Color(0xFF080808), Color.White, Color(0xFFE31B23), null, "MONSTER JAM", remote("monsterjam.com"))
    "RUGBYPASS TV" -> BrandSpec(Color(0xFF073B2A), Color.White, Color(0xFF49D17D), null, "RUGBYPASS", remote("rugbypass.com"))
    else -> BrandSpec(Color(0xFF151A22), Color.White, Color(0xFFFF1838), null, key.take(10))
}

private fun loadSvgBitmap(context: Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val bitmap = Bitmap.createBitmap(width.coerceAtLeast(1), height.coerceAtLeast(1), Bitmap.Config.ARGB_8888)
    SVG.getFromAsset(context.assets, "brand_logos/$asset.svg").renderToCanvas(AndroidCanvas(bitmap))
    bitmap
}.getOrNull()

private suspend fun loadRemoteBitmap(url: String, width: Int, height: Int): Bitmap? = withContext(Dispatchers.IO) {
    runCatching {
        val connection = (URL(url).openConnection() as HttpURLConnection).apply { connectTimeout=2500; readTimeout=5000; instanceFollowRedirects=true; setRequestProperty("User-Agent","XSportsX/1.5") }
        try { if(connection.responseCode !in 200..299) return@runCatching null; val source=connection.inputStream.use{BitmapFactory.decodeStream(it)} ?: return@runCatching null; Bitmap.createScaledBitmap(source,width.coerceAtLeast(1),height.coerceAtLeast(1),true) } finally { connection.disconnect() }
    }.getOrNull()
}

@Composable
private fun LocalSvgLogo(asset: String, modifier: Modifier, size: Dp, description: String) {
    val context=LocalContext.current; val px=with(LocalDensity.current){size.toPx().roundToInt().coerceAtLeast(1)}; val bitmap=remember(asset,px){loadSvgBitmap(context,asset,px,px)}
    if(bitmap!=null) Image(bitmap.asImageBitmap(),description,modifier.size(size),contentScale=ContentScale.Fit)
}

@Composable
private fun RemoteBrandLogo(url: String, modifier: Modifier, size: Dp, description: String) {
    val px=with(LocalDensity.current){size.toPx().roundToInt().coerceAtLeast(1)}; val state=produceState<Bitmap?>(null,url,px){value=loadRemoteBitmap(url,px,px)}
    state.value?.let{Image(it.asImageBitmap(),description,modifier.size(size),contentScale=ContentScale.Fit)}
}

@Composable
private fun VectorBrandMark(spec: BrandSpec, size: Dp) {
    Box(Modifier.size(size),contentAlignment=Alignment.Center){
        Canvas(Modifier.fillMaxSize()) {
            val w=size.toPx(); val h=size.toPx(); val c=center
            when(spec.mark){
                "SEC"->{drawCircle(spec.accent,w*.30f,c);drawCircle(spec.bg,w*.22f,c,style=Stroke(width=5f))}
                "ACC"->drawLine(spec.accent,Offset(w*.18f,h*.72f),Offset(w*.82f,h*.28f),8f)
                "B1G"->drawRoundRect(spec.accent,Offset(w*.14f,h*.28f),Size(w*.72f,h*.44f),CornerRadius(8f,8f),style=Stroke(width=6f))
                "FS1"->drawOval(Color.White,Offset(w*.13f,h*.27f),Size(w*.74f,h*.46f),style=Stroke(width=5f))
                else->{drawCircle(spec.accent,w*.30f,c);drawCircle(spec.bg,w*.21f,c,style=Stroke(width=5f))}
            }
        }
        Text(spec.mark,color=spec.fg,fontSize=if(spec.mark.length>6)7.sp else 14.sp,fontWeight=FontWeight.Black,textAlign=TextAlign.Center,maxLines=1)
    }
}

@Composable
private fun BrandBox(spec: BrandSpec, size: Dp, description: String) {
    Box(Modifier.size(size).clip(RoundedCornerShape(size/3)).background(spec.bg).border(1.dp,spec.accent.copy(alpha=.9f),RoundedCornerShape(size/3)),contentAlignment=Alignment.Center){
        when{spec.asset!=null->LocalSvgLogo(spec.asset,Modifier,size*.78f,description);spec.remote!=null->RemoteBrandLogo(spec.remote,Modifier,size*.82f,description);else->VectorBrandMark(spec,size*.78f)}
    }
}

@Composable fun XSportsLeagueLogo(name:String,modifier:Modifier=Modifier,size:Dp=72.dp){val key=name.uppercase();Box(modifier,contentAlignment=Alignment.Center){BrandBox(spec(key),size,name)}}

@Composable fun XSportsNetworkLogo(name:String,modifier:Modifier=Modifier,size:Dp=52.dp){val key=name.uppercase();val s=networkSpec(key);Box(modifier,contentAlignment=Alignment.Center){BrandBox(s,size,name);if(key=="ESPN2"||key=="ESPNU"||key=="ESPN+")Text(key.removePrefix("ESPN"),color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Black,modifier=Modifier.align(Alignment.BottomEnd).background(Color(0xFF090909)).padding(horizontal=2.dp,vertical=1.dp))}}
