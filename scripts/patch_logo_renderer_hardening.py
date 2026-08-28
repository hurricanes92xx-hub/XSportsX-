#!/usr/bin/env python3
from pathlib import Path

p = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt')
s = p.read_text(encoding='utf-8')

# The previous renderer normalized remote bitmaps but rendered bundled SVGs
# directly into a square. SVGs with unusual viewBoxes therefore appeared
# oversized/distorted. Render everything to a large transparent canvas, trim
# transparent margins, then fit the visible artwork into the requested box.
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
    raise SystemExit('loadSvgBitmap block not found')
s = s.replace(old, new)

# Use the same trim/fit path for remote images; this removes transparent
# gutters and makes wide wordmarks occupy a consistent fraction of the card.
s = s.replace('bitmap?.let{fitBitmap(it,width,height)}', 'bitmap?.let{trimAndFit(it,width,height)}')

# Normalize display names before selecting a brand. Schedule feeds frequently
# use long names/aliases instead of the short card label.
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
    raise SystemExit('logo composables block not found')
s = s.replace(old2, new2)
p.write_text(s, encoding='utf-8')
print('Hardened local/remote logo normalization and alias resolution.')
