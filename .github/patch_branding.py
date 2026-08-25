from pathlib import Path

# Mobile: use the same animated XtremeLogo composable as the TV surface.
mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
ms = mobile.read_text()
if 'MobileHeader' in ms:
    marker = 'private fun MobileHeader(sourceConfigured: Boolean, pulseAlpha: Float, onConnect: () -> Unit) {'
    start = ms.index(marker)
    end = ms.index('\n}\n\n@Composable\nprivate fun MobileHomeContent', start) + 2
    block = ms[start:end]
    if 'XtremeLogo(size = 46.dp)' in block:
        block = block.replace('XtremeLogo(size = 46.dp)', 'XtremeLogo(size = 56.dp)', 1)
    elif 'XtremeLogo(size = 56.dp)' not in block:
        old = '    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {\n        Column(Modifier.weight(1f)) {'
        new = '    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {\n        XtremeLogo(size = 56.dp)\n        Spacer(Modifier.width(10.dp))\n        Column(Modifier.weight(1f)) {'
        if old not in block:
            raise SystemExit('MobileHeader anchor not found')
        block = block.replace(old, new, 1)
    ms = ms[:start] + block + ms[end:]
mobile.write_text(ms)

# TV: replace any remaining text-only brand mark and keep the animated logo prominent.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
old_nav = 'Row(verticalAlignment = Alignment.CenterVertically) { Text("X", color = TvRed, fontSize = 46.sp, fontWeight = FontWeight.Black); Text("SPORTS", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Black); Text("X", color = TvRed, fontSize = 25.sp, fontWeight = FontWeight.Black) }'
new_nav = 'Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterStart) { XtremeLogo(size = 72.dp) }'
if old_nav in ts:
    ts = ts.replace(old_nav, new_nav, 1)
ts = ts.replace('XtremeLogo(size = 42.dp)', 'XtremeLogo(size = 56.dp)', 1)
old_top = 'Text("XSPORTSX", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Black)'
if old_top in ts:
    ts = ts.replace(old_top, 'XtremeLogo(size = 56.dp)', 1)
tv.write_text(ts)
