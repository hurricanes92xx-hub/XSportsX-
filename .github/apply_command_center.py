from pathlib import Path

mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = mobile.read_text()
mobile_anchor = 'MobileHeader(sourceConfigured, alpha, onConnect)\n                    Spacer(Modifier.height(16.dp))'
mobile_insert = 'MobileHeader(sourceConfigured, alpha, onConnect)\n                    Spacer(Modifier.height(16.dp))\n                    XtremeCommandCenterMobile(sourceConfigured, onConnect)\n                    Spacer(Modifier.height(18.dp))'
if 'XtremeCommandCenterMobile(sourceConfigured, onConnect)' not in s:
    if mobile_anchor not in s:
        raise SystemExit('Mobile Command Center anchor not found; refusing to patch')
    s = s.replace(mobile_anchor, mobile_insert, 1)
    mobile.write_text(s)

# TV: only add the Command Center to the HOME screen, preserving the existing live-game and ticker logic.
tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
tv_anchor = '"HOME" -> { TvHero(onConnect); Spacer(Modifier.height(18.dp));'
tv_insert = '"HOME" -> { TvHero(onConnect); Spacer(Modifier.height(18.dp)); XtremeCommandCenterTv(liveGames.size, onConnect); Spacer(Modifier.height(18.dp));'
if 'XtremeCommandCenterTv(liveGames.size, onConnect)' not in ts:
    if tv_anchor not in ts:
        raise SystemExit('TV Command Center anchor not found; refusing to patch')
    ts = ts.replace(tv_anchor, tv_insert, 1)
    tv.write_text(ts)

print('Command Center patch applied safely')
