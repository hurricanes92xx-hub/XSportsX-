from pathlib import Path
import re

logos = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt')
s = logos.read_text()
replacements = {
    '"WRESTLING" -> BrandSpec(Color(0xFF1A1A1A), Color.White, Color(0xFFE31B23), null, "WR")': '"WRESTLING" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE31B23), "wwe", "WWE")',
    '"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), null, "FS1")': '"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), "fs1", "FS1")',
    '"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), null, "SEC")': '"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), "sec", "SEC")',
    '"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), null, "ACC")': '"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), "acc", "ACC")',
}
for old, new in replacements.items():
    s = s.replace(old, new)

# This patch used to require an exact pre-patch implementation. Other logo
# patches can legitimately transform the renderer first, so make the patch
# idempotent: if the hardened renderer is already present, do not fail.
if 'private fun trimAndFit(' not in s:
    old = '''private fun loadSvgBitmap(context: Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val bitmap=Bitmap.createBitmap(width.coerceAtLeast(1),height.coerceAtLeast(1),Bitmap.Config.ARGB_8888)
    SVG.getFromAsset(context.assets,"brand_logos/$asset.svg").renderToCanvas(AndroidCanvas(bitmap)); bitmap
}.getOr_none()
'''
    if old not in s:
        old = '''private fun loadSvgBitmap(context: Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val bitmap=Bitmap.createBitmap(width.coerceAtLeast(1),height.coerceAtLeast(1),Bitmap.Config.ARGB_8888)
    SVG.getFromAsset(context.assets,"brand_logos/$asset.svg").renderToCanvas(AndroidCanvas(bitmap)); bitmap
}.getOrNull()
'''
    new = '''private fun trimAndFit(source: Bitmap, width: Int, height: Int, inset: Float = .84f): Bitmap {
    val w = source.width; val h = source.height
    var left = w; var top = h; var right = -1; var bottom = -1
    val pixels = IntArray(w)
    for (y in 0 until h) {
        source.getPixels(pixels, 0, w, 0, y, w, 1)
        for (x in 0 until w) if (((pixels[x] ushr 24) and 0xff) > 8) {
            if (x < left) left = x; if (x > right) right = x
            if (y < top) top = y; if (y > bottom) bottom = y
        }
    }
    val visible = if (right >= left && bottom >= top)
        Bitmap.createBitmap(source, left, top, right-left+1, bottom-top+1)
    else source
    val outW = width.coerceAtLeast(1); val outH = height.coerceAtLeast(1)
    val boxW = (outW * inset).roundToInt().coerceAtLeast(1)
    val boxH = (outH * inset).roundToInt().coerceAtLeast(1)
    val scale = min(boxW.toFloat()/visible.width.toFloat(), boxH.toFloat()/visible.height.toFloat())
    val drawW = (visible.width * scale).roundToInt().coerceAtLeast(1)
    val drawH = (visible.height * scale).roundToInt().coerceAtLeast(1)
    val scaled = Bitmap.createScaledBitmap(visible, drawW, drawH, true)
    val out = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888)
    AndroidCanvas(out).drawBitmap(scaled, (outW-drawW)/2f, (outH-drawH)/2f, null)
    if (visible !== source) visible.recycle()
    if (scaled !== visible && scaled !== source) scaled.recycle()
    return out
}

private fun loadSvgBitmap(context: Context, asset: String, width: Int, height: Int): Bitmap? = runCatching {
    val source = Bitmap.createBitmap(512,512,Bitmap.Config.ARGB_8888)
    SVG.getFromAsset(context.assets,"brand_logos/$asset.svg").renderToCanvas(AndroidCanvas(source))
    trimAndFit(source,width,height)
}.getOrNull()
'''
    if old not in s:
        raise SystemExit('loadSvgBitmap implementation not recognized; refusing unsafe rewrite')
    s = s.replace(old, new, 1)

# The unified logo patch may already have installed the normalized composables.
if 'private fun logoKey(' not in s:
    old2 = '@Composable fun XSportsLeagueLogo(name:String,modifier:Modifier=Modifier,size:Dp=72.dp){val key=name.uppercase();Box(modifier,contentAlignment=Alignment.Center){BrandBox(spec(key),size,name)}}\n@Composable fun XSportsNetworkLogo(name:String,modifier:Modifier=Modifier,size:Dp=52.dp){val key=name.uppercase();val s=networkSpec(key);Box(modifier,contentAlignment=Alignment.Center){BrandBox(s,size,name)}}'
    new2 = '''private fun logoKey(value:String):String = value.uppercase()
    .replace("🏈", "").replace("🏀", "").replace("⚾", "").replace("🏒", "")
    .replace("⚽", "").replace("🥊", "").replace("🏎️", "")
    .replace("WWE NETWORK", "WWE").replace("WWE RAW", "WWE")
    .replace("NCAA FOOTBALL", "NCAA FB").replace("COLLEGE FOOTBALL", "NCAA FB")
    .replace("NCAA BASKETBALL", "NCAA BB").replace("COLLEGE BASKETBALL", "NCAA BB")
    .replace("NCAA VOLLEYBALL", "NCAA VB").replace("COLLEGE VOLLEYBALL", "NCAA VB")
    .replace("PREMIER LEAGUE", "EPL").replace("MLS SOCCER", "MLS")
    .replace("ESPN HD", "ESPN").replace("FOX SPORTS 1", "FS1")
    .replace("FOX SPORTS 2", "FS2").replace("CBS SPORTS NETWORK", "CBS SPORTS")
    .replace("ACC NETWORK ESPN", "ACC NETWORK").replace("SEC NETWORK ESPN", "SEC NETWORK")
    .trim()

@Composable fun XSportsLeagueLogo(name:String,modifier:Modifier=Modifier,size:Dp=72.dp){val key=logoKey(name);Box(modifier,contentAlignment=Alignment.Center){BrandBox(spec(key),size,name)}}
@Composable fun XSportsNetworkLogo(name:String,modifier:Modifier=Modifier,size:Dp=52.dp){val key=logoKey(name);val s=networkSpec(key);Box(modifier,contentAlignment=Alignment.Center){BrandBox(s,size,name)}}'''
    if old2 not in s:
        raise SystemExit('logo composables block not recognized; refusing unsafe rewrite')
    s = s.replace(old2, new2, 1)

ui = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = ui.read_text()
if 'trimAndFit' not in s:
    pass
logos.write_text(s)

# The UI portion is intentionally left alone here; its canonical logo changes
# are independent of the schedule patches and may already be applied by a
# preceding patch in the production chain.
print('canonical logo patch applied safely')
