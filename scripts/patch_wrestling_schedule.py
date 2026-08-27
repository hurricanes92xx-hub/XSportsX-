from pathlib import Path

TV = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
MOBILE = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')

# TV: add WRESTLING to the sports rail and route it to the shared schedule.
# Keep this patch idempotent and independent of the current catalog ordering/size.
t = TV.read_text()

if 'TvSport("WRESTLING","WWE"' not in t:
    marker = 'private val tvSports = listOf('
    start = t.find(marker)
    if start < 0:
        raise SystemExit('TV sports catalog not found')
    close = t.find('\n)', start)
    if close < 0:
        raise SystemExit('TV sports catalog terminator not found')
    # Insert into the existing expanded catalog instead of replacing it with an
    # obsolete hard-coded list.
    t = t[:close] + ',TvSport("WRESTLING","WWE","")' + t[close:]

if '"WRESTLING"->{TvSection("WRESTLING"' not in t:
    marker = '                    "SETTINGS"->TvSettings{onConnect()}'
    replacement = '                    "WRESTLING"->{TvSection("WRESTLING","WWE • AEW • TNA");WrestlingScheduleSection{onConnect()}}\n' + marker
    if marker not in t:
        raise SystemExit('TV SETTINGS route changed; refusing unsafe insertion')
    t = t.replace(marker, replacement, 1)
TV.write_text(t)

# Mobile: put the shared schedule directly beneath the existing UP NEXT rail.
m = MOBILE.read_text()
if 'WrestlingScheduleSection{onConnect()}' not in m:
    needle = 'Spacer(Modifier.height(20.dp)); MobileSectionLabel("UP NEXT", "SPORTS FEED"); Spacer(Modifier.height(8.dp)); UpcomingStrip()'
    replacement = needle + '; Spacer(Modifier.height(20.dp)); WrestlingScheduleSection{onConnect()}'
    if needle not in m:
        raise SystemExit('Mobile home layout changed; refusing unsafe insertion')
    m = m.replace(needle, replacement, 1)
MOBILE.write_text(m)
print('Wrestling schedule wired into Mobile + TV')
