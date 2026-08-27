from pathlib import Path

MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
SCHEDULE = Path("app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt")

# Idempotent: never fail the release build because a previous UI patch already
# changed the formatting or routing hook.
if MOBILE.exists():
    text = MOBILE.read_text()
    text = text.replace(
        'fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {})',
        'fun FuturisticHome(onConnect: () -> Unit = {}, onNetwork: (XNetwork) -> Unit = {}, onSportLeague: (String) -> Unit = {})'
    )
    text = text.replace(
        'MobileHomeContent(sourceConfigured, onConnect, onNetwork)',
        'MobileHomeContent(sourceConfigured, onConnect, onNetwork, onSportLeague)'
    )
    text = text.replace(
        'private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit)',
        'private fun MobileHomeContent(sourceConfigured: Boolean, onConnect: () -> Unit, onNetwork: (XNetwork) -> Unit, onSportLeague: (String) -> Unit)'
    )
    text = text.replace(
        'SportBadgeCard(sport) { onConnect() }',
        'SportBadgeCard(sport) { onSportLeague(SportsScheduleService.canonicalLeagueFor(sport.name)) }'
    )
    MOBILE.write_text(text)

if SCHEDULE.exists():
    text = SCHEDULE.read_text()
    old = 'listOf("ALL", "NFL", "NCAA FB", "NBA", "NCAA BB", "MLB", "NHL", "UFC", "BOXING")'
    if old in text:
        text = text.replace(old, 'listOf("ALL") + SportsScheduleService.uiLeagueChoices', 1)
    SCHEDULE.write_text(text)

print("Top Sports UI patch complete")
