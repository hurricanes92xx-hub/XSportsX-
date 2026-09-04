#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, pattern: str, replacement: str, flags: int = 0) -> bool:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"UI repair pattern not found exactly once: {path}")
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def patch_sports_logos() -> bool:
    path = ROOT / "app/src/main/java/com/xsportsx/app/SportsLogos.kt"
    text = path.read_text(encoding="utf-8")
    original = text
    text = text.replace(
        '"UFC" -> BrandSpec("ufc", "UFC", Color(0xFF05070A), Color(0xFFFF1744), "https://commons.wikimedia.org/wiki/Special:FilePath/UFC_Logo.svg?width=256")',
        '"UFC" -> BrandSpec("ufc", "UFC", Color(0xFF05070A), Color(0xFFFF1744), "")'
    )
    text = text.replace(
        '"MLB" -> BrandSpec("mlb", "MLB", Color(0xFF041E42), Color(0xFFEE1C25), "")',
        '"MLB" -> BrandSpec("mlb", "MLB", Color(0xFF16395F), Color(0xFFEE1C25), "")'
    )
    old = '''@Composable\nprivate fun BrandBox(spec: BrandSpec, modifier: Modifier, size: Dp) {\n    Box(\n        modifier = modifier\n            .clip(RoundedCornerShape(size / 3))\n            .background(spec.background),\n        contentAlignment = Alignment.Center\n    ) {\n        if (spec.asset != null) {\n            LocalSvgLogo(spec.asset, Modifier.fillMaxSize().padding(size * .10f))\n        } else if (spec.remote.isNotBlank()) {\n            RemoteBrandLogo(spec, Modifier.fillMaxSize().padding(size * .10f))\n        } else {\n            VectorBrandMark(spec, Modifier.fillMaxSize().padding(size * .12f))\n        }\n    }\n}'''
    new = '''@Composable\nprivate fun BrandBox(spec: BrandSpec, modifier: Modifier, size: Dp) {\n    Box(\n        modifier = modifier\n            .clip(RoundedCornerShape(size / 3))\n            .background(spec.background),\n        contentAlignment = Alignment.Center\n    ) {\n        // Always render a deterministic local mark first. If a bundled asset is\n        // missing/corrupt, the fallback remains visible instead of a blank tile.\n        VectorBrandMark(spec, Modifier.fillMaxSize().padding(size * .12f))\n        if (spec.asset != null) {\n            LocalSvgLogo(spec.asset, Modifier.fillMaxSize().padding(size * .10f))\n        } else if (spec.remote.isNotBlank()) {\n            RemoteBrandLogo(spec, Modifier.fillMaxSize().padding(size * .10f))\n        }\n    }\n}'''
    if old not in text:
        raise SystemExit("BrandBox contract not found")
    text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_schedule_card() -> bool:
    path = ROOT / "app/src/main/java/com/xsportsx/app/LeagueScheduleScreen.kt"
    replacement = '''@Composable\nprivate fun LeagueEventCard(event: SportsEvent, onWatch: () -> Unit) {\n    Column(\n        Modifier.fillMaxWidth()\n            .clip(RoundedCornerShape(16.dp))\n            .background(Color(0xFF10141C))\n            .padding(12.dp)\n    ) {\n        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {\n            Box(Modifier.size(56.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF080B11)), contentAlignment = Alignment.Center) {\n                if (event.artUrl.isNotBlank()) {\n                    AsyncImage(model = event.artUrl, contentDescription = event.league, modifier = Modifier.fillMaxSize().padding(9.dp), contentScale = ContentScale.Fit)\n                } else {\n                    XSportsLeagueLogo(event.league, size = 42.dp)\n                }\n            }\n            Spacer(Modifier.width(12.dp))\n            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {\n                if (event.away.isNotBlank() && event.home.isNotBlank()) {\n                    TeamLine(event.away, event.awayLogo, "AWAY")\n                    TeamLine(event.home, event.homeLogo, "HOME")\n                } else {\n                    Text(event.title.ifBlank { event.league }, color = Color.White, fontWeight = FontWeight.Black, maxLines = 2, overflow = TextOverflow.Ellipsis)\n                }\n            }\n        }\n        Spacer(Modifier.height(8.dp))\n        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {\n            Column(Modifier.weight(1f)) {\n                Text(if (event.isLive) "LIVE • ${event.status.ifBlank { event.state }}" else formatTime(event.startUtc), color = if (event.isLive) Color(0xFFFF536C) else Color(0xFF7F8795), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)\n                if (event.broadcast.isNotBlank()) Text(event.broadcast, color = Color(0xFF9BA4B2), fontSize = 9.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)\n            }\n            if (event.isLive) {\n                Button(onClick = onWatch, colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF1744)), contentPadding = PaddingValues(horizontal = 14.dp, vertical = 0.dp)) { Text("WATCH", fontSize = 10.sp, fontWeight = FontWeight.Black) }\n            } else {\n                Surface(color = Color(0xFF171C26), shape = RoundedCornerShape(8.dp)) {\n                    Text("UPCOMING", color = Color(0xFF9BA4B2), fontSize = 8.sp, fontWeight = FontWeight.Black, modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp))\n                }\n            }\n        }\n    }\n}\n\n@Composable\nprivate fun TeamLine(name: String, logo: String, label: String) {\n    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {\n        Box(Modifier.size(30.dp), contentAlignment = Alignment.Center) {\n            if (logo.isNotBlank()) AsyncImage(model = logo, contentDescription = name, modifier = Modifier.size(28.dp), contentScale = ContentScale.Fit)\n            else XSportsLeagueLogo(name, size = 26.dp)\n        }\n        Spacer(Modifier.width(7.dp))\n        Text(name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))\n        Spacer(Modifier.width(6.dp))\n        Text(label, color = Color(0xFF667080), fontSize = 8.sp, fontWeight = FontWeight.Black, modifier = Modifier.widthIn(min = 32.dp))\n    }\n}\n\nprivate fun dayLabel'''
    return replace_once(path, r'@Composable\nprivate fun LeagueEventCard[\s\S]*?\nprivate fun dayLabel', replacement)


def patch_league_filter() -> bool:
    path = ROOT / "app/src/main/java/com/xsportsx/app/ScheduleSnapshotRepository.kt"
    text = path.read_text(encoding="utf-8")
    original = text
    old = '''        return all(force).asSequence().filter { !it.isLive }\n            .filter { event -> canonical == null || SportsScheduleService.canonicalLeagueFor(event.league) == canonical }'''
    new = '''        return all(force).asSequence().filter { !it.isLive }\n            .filter { event ->\n                if (canonical == null) true\n                else if (canonical.equals("WRESTLING", true)) {\n                    event.league.equals("WWE", true) || event.league.equals("AEW", true) ||\n                        event.league.equals("TNA", true) || event.league.equals("AAA Wrestling", true) ||\n                        event.league.equals("WRESTLING", true)\n                } else SportsScheduleService.canonicalLeagueFor(event.league) == canonical\n            }'''
    if old not in text:
        raise SystemExit("league filter contract not found")
    text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_stream_resolution() -> bool:
    path = ROOT / "app/src/main/java/com/xsportsx/app/LiveChannelsScreen.kt"
    text = path.read_text(encoding="utf-8")
    original = text
    old = '''                        selectedEvent != null -> {\n                            // Authorized Xtream is Tier 0: cached-first, then bounded category lookup.\n                            val fast = fastXtream.resolve(selectedEvent!!)\n                            if (fast.isNotEmpty()) fast else StreamResolver(context).loadMatchingEventStreams(selectedEvent!!, force)\n                        }'''
    new = '''                        selectedEvent != null -> {\n                            // Run authorized Xtream and public/learned discovery together.\n                            // Never make a slow Xtream cold-cache request block all other sources.\n                            kotlinx.coroutines.coroutineScope {\n                                val xtreamJob = async(Dispatchers.IO) { fastXtream.resolve(selectedEvent!!) }\n                                val publicJob = async(Dispatchers.IO) { StreamResolver(context).loadMatchingEventStreams(selectedEvent!!, force) }\n                                val xtream = xtreamJob.await()\n                                if (xtream.isNotEmpty()) {\n                                    publicJob.cancel()\n                                    xtream\n                                } else {\n                                    publicJob.await()\n                                }\n                            }\n                        }'''
    if old not in text:
        raise SystemExit("stream resolution contract not found")
    text = text.replace(old, new)
    text = text.replace('import kotlinx.coroutines.launch\nimport kotlinx.coroutines.withTimeoutOrNull', 'import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.async\nimport kotlinx.coroutines.launch\nimport kotlinx.coroutines.withTimeoutOrNull')
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_ticker_placement() -> bool:
    path = ROOT / "app/src/main/java/com/xsportsx/app/MainActivityFuture.kt"
    text = path.read_text(encoding="utf-8")
    original = text
    old = '''                        TvPairButton(connected = connected, onClick = { if (connected) mobilePair = true else connectSource = true }, modifier = Modifier.align(Alignment.TopEnd).padding(top = 20.dp, end = 24.dp))\n                        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).padding(bottom = 2.dp))'''
    new = '''                        TvPairButton(connected = connected, onClick = { if (connected) mobilePair = true else connectSource = true }, modifier = Modifier.align(Alignment.TopEnd).padding(top = 20.dp, end = 24.dp))'''
    if old not in text:
        raise SystemExit("ticker overlay contract not found")
    text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for name, fn in [\n        ("SportsLogos", patch_sports_logos),\n        ("LeagueSchedule", patch_schedule_card),\n        ("LeagueFilter", patch_league_filter),\n        ("StreamResolution", patch_stream_resolution),\n        ("TickerPlacement", patch_ticker_placement),\n    ]:\n        if fn(): changed.append(name)\n    print("ANDROID_UI_REPAIR:" + (" changed=" + ",".join(changed) if changed else " already-compliant"))

if __name__ == "__main__":
    main()
