from pathlib import Path

path = Path("app/src/main/java/com/xsportsx/app/SportsScheduleService.kt")
text = path.read_text()

needle = '    val isUpcoming:Boolean get()=state.equals("pre",true)||state.equals("scheduled",true)||state.equals("upcoming",true)\n'
replacement = needle + '    fun isPregame(nowMillis:Long=System.currentTimeMillis()):Boolean {\n        val start=runCatching{java.time.Instant.parse(startUtc).toEpochMilli()}.getOrDefault(0L)\n        return start > nowMillis && start <= nowMillis + 30L*60L*1000L && !isLive\n    }\n'
if 'fun isPregame(nowMillis:Long=' not in text:
    if needle not in text: raise SystemExit('SportsEvent state block not found')
    text=text.replace(needle,replacement,1)

old='results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc})'
new='results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isPregame()||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!(it.isLive||it.isPregame())}.thenBy{it.startUtc})'
if old in text:
    text=text.replace(old,new,1)

path.write_text(text)
print('30-minute pregame window added')
