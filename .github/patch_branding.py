from pathlib import Path

# Mobile: use the same XtremeLogo composable as the TV/desktop surfaces.
mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
ms = mobile.read_text()
if 'MobileHeader' in ms and 'XtremeLogo(size = 46.dp)' not in ms:
    marker = 'private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit) {'
    start = ms.index(marker)
    end = ms.index('\n}\n\n@Composable\nprivate fun MobileHomeContent', start) + 2
    block = ms[start:end]
    old = '    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {\n        Column(Modifier.weight(1f)) {'
    new = '    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {\n        XtremeLogo(size = 46.dp)\n        Spacer(Modifier.width(10.dp))\n        Column(Modifier.weight(1f)) {'
    if old not in block:
        raise SystemExit('MobileHeader anchor not found')
    ms = ms[:start] + block.replace(old, new, 1) + ms[end:]
mobile.write_text(ms)

# TV: replace the text-only brand marks with the same actual logo.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
old_nav = 'Row(verticalAlignment = Alignment.CenterVertically) { Text("X", color = TvRed, fontSize = 46.sp, fontWeight = FontWeight.Black); Text("SPORTS", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Black); Text("X", color = TvRed, fontSize = 25.sp, fontWeight = FontWeight.Black) }'
new_nav = 'Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterStart) { XtremeLogo(size = 72.dp) }'
if old_nav in ts:
    ts = ts.replace(old_nav, new_nav, 1)
old_top = 'Text("XSPORTSX", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)'
new_top = 'XtremeLogo(size = 42.dp)'
if old_top in ts:
    ts = ts.replace(old_top, new_top, 1)
tv.write_text(ts)
