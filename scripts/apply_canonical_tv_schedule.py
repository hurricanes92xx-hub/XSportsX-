#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
text = path.read_text(encoding="utf-8")
start = text.index("private suspend fun loadTvGames")
end = text.index("@Composable fun TvHome", start)
replacement = '''private suspend fun loadTvGames(liveOnly:Boolean=true):List<TvGame> = withContext(Dispatchers.IO) {
    val events=runCatching { SportsScheduleService.load() }.getOrDefault(emptyList())
    events.asSequence()
        .filter { event -> if (liveOnly) event.isLive else !event.isLive && event.isUpcoming }
        .map { event ->
            val start=runCatching { java.time.Instant.parse(event.startUtc).toEpochMilli() }.getOrDefault(System.currentTimeMillis())
            TvGame(
                league=event.league,
                home=event.home.ifBlank { "TBD" },
                away=event.away.ifBlank { "TBD" },
                homeLogo=event.homeLogo,
                awayLogo=event.awayLogo,
                score=if (event.isLive) event.status.ifBlank { "LIVE" } else "—",
                status=if (event.isLive) event.status.ifBlank { event.state.ifBlank { "LIVE" } } else event.status.ifBlank { "UPCOMING" },
                network=event.broadcast.ifBlank { "TBD" },
                live=event.isLive,
                timestamp=start
            )
        }
        .sortedBy { it.timestamp }
        .toList()
}

'''
imports = "import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.withContext\n"
if "import kotlinx.coroutines.Dispatchers" not in text:
    marker = "import kotlinx.coroutines.awaitAll\n"
    if marker in text:
        text = text.replace(marker, marker + imports, 1)
    else:
        text = text.replace("import kotlinx.coroutines.async\n", "import kotlinx.coroutines.async\n" + imports, 1)
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("TV schedule source patched to SportsScheduleService with coroutine IO imports")
