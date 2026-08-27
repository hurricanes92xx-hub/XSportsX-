from pathlib import Path

TV = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
MOBILE = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')

# TV: add WRESTLING to the sports rail and route it to the shared schedule.
t = TV.read_text()
old = 'private val tvSports = listOf(TvSport("NFL","NFL"),TvSport("NBA","NBA"),TvSport("NCAA FB","NCAA"),TvSport("NCAA BB","NCAA"),TvSport("MLB","MLB"),TvSport("NHL","NHL"),TvSport("UFC","UFC"),TvSport("BOXING","BOX"))'
new = 'private val tvSports = listOf(TvSport("NFL","NFL"),TvSport("NBA","NBA"),TvSport("NCAA FB","NCAA"),TvSport("NCAA BB","NCAA"),TvSport("MLB","MLB"),TvSport("NHL","NHL"),TvSport("UFC","UFC"),TvSport("BOXING","BOX"),TvSport("WRESTLING","WWE"))'
if 'TvSport("WRESTLING","WWE")' not in t:
    if old not in t:
        raise SystemExit('TV sports list changed; refusing unsafe replacement')
    t=t.replace(old,new,1)

if '"WRESTLING"->{TvSection("WRESTLING"' not in t:
    marker='                    "SETTINGS"->TvSettings{onConnect()}'
    replacement='                    "WRESTLING"->{TvSection("WRESTLING","WWE • AEW • TNA");WrestlingScheduleSection{onConnect()}}\n'+marker
    if marker not in t:
        raise SystemExit('TV SETTINGS route changed; refusing unsafe insertion')
    t=t.replace(marker,replacement,1)
TV.write_text(t)

# Mobile: put the shared schedule directly beneath the existing UP NEXT rail.
m=MOBILE.read_text()
needle='Spacer(Modifier.height(20.dp)); MobileSectionLabel("UP NEXT", "SPORTS FEED"); Spacer(Modifier.height(8.dp)); UpcomingStrip()'
replacement=needle+'; Spacer(Modifier.height(20.dp)); WrestlingScheduleSection{onConnect()}'
if 'WrestlingScheduleSection{onConnect()}' not in m:
    if needle not in m:
        raise SystemExit('Mobile home layout changed; refusing unsafe insertion')
    m=m.replace(needle,replacement,1)
MOBILE.write_text(m)
print('Wrestling schedule wired into Mobile + TV')
