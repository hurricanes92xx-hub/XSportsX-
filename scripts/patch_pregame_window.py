from pathlib import Path

service = Path("app/src/main/java/com/xsportsx/app/SportsScheduleService.kt")
model = Path("app/src/main/java/com/xsportsx/app/SportsEvent.kt")

pregame = '''\n    fun isPregame(nowMillis:Long=System.currentTimeMillis()):Boolean {\n        val start=runCatching{java.time.Instant.parse(startUtc).toEpochMilli()}.getOrDefault(0L)\n        return start > nowMillis && start <= nowMillis + 30L*60L*1000L && !isLive\n    }\n'''

# New builds keep event state in SportsEvent.kt. Patch the model directly so the
# service remains focused on fetching/normalizing schedule data.
if model.exists():
    text = model.read_text()
    if 'fun isPregame(nowMillis:Long=' not in text:
        marker = '\n    val isUpcoming: Boolean'
        if marker in text:
            text = text.replace(marker, pregame + marker, 1)
        else:
            raise SystemExit('SportsEvent model insertion point not found')
    model.write_text(text)
else:
    # Legacy compatibility for branches that still embed event state in the service.
    text = service.read_text()
    needle = '    val isUpcoming:Boolean get()=state.equals("pre",true)||state.equals("scheduled",true)||state.equals("upcoming",true)\n'
    replacement = needle + '    fun isPregame(nowMillis:Long=System.currentTimeMillis()):Boolean {\n        val start=runCatching{java.time.Instant.parse(startUtc).toEpochMilli()}.getOrDefault(0L)\n        return start > nowMillis && start <= nowMillis + 30L*60L*1000L && !isLive\n    }\n'
    if 'fun isPregame(nowMillis:Long=' not in text:
        if needle not in text:
            raise SystemExit('Legacy SportsEvent state block not found')
        text=text.replace(needle,replacement,1)
    service.write_text(text)

# Make the service include the pregame window when the legacy expression exists.
text = service.read_text()
old='results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!it.isLive}.thenBy{it.startUtc})'
new='results.flatten().distinctBy{it.id.ifBlank{it.title+it.startUtc+it.league}}.filter{it.isLive||it.isPregame()||it.isUpcoming}.sortedWith(compareBy<SportsEvent>{!(it.isLive||it.isPregame())}.thenBy{it.startUtc})'
if old in text:
    text=text.replace(old,new,1)
service.write_text(text)
print('30-minute pregame window added safely')
