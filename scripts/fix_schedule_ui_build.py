#!/usr/bin/env python3
from pathlib import Path
import re

SCREEN = Path('app/src/main/java/com/xsportsx/app/SportsScheduleScreen.kt')
s = SCREEN.read_text(encoding='utf-8')

# The yearly schedule patch intentionally collapses the league list to a
# one-line expression. The later coverage patch previously searched for a
# multiline list terminator and could accidentally consume the LazyRow opener.
# Normalize the generated screen after all schedule patches have run.
choices = '''    val leagueChoices = listOf(
        "ALL", "NFL", "NBA", "WNBA", "NCAA FB", "NCAA FCS", "NCAA BB", "NCAA WBB",
        "MLB", "NCAA BASEBALL", "NHL", "NCAA MEN HOCKEY", "NCAA WOMEN HOCKEY", "NCAA SOFTBALL",
        "NCAA VB", "NCAA MEN SOCCER", "NCAA WOMEN SOCCER", "NCAA MEN LAX", "NCAA WOMEN LAX", "NCAA WRESTLING",
        "MLS", "EPL", "LaLiga", "Bundesliga", "Serie A", "Ligue 1", "UCL", "UEL", "NWSL",
        "UFC", "BOXING", "RUGBY", "F1", "NASCAR", "INDYCAR", "WRESTLING", "WRC", "WEC", "IMSA",
        "FORMULA E", "MXGP", "MONSTER JAM", "MOTOGP"
    )'''

# Prefer the current one-line generated form; otherwise replace a complete
# multiline list only when its own closing line is present.
if '    val leagueChoices = listOf("ALL") + SportsScheduleService.uiLeagueChoices' in s:
    s = re.sub(
        r'^    val leagueChoices = .*?$\n',
        choices + '\n',
        s,
        count=1,
        flags=re.MULTILINE,
    )
else:
    pattern = re.compile(r'(?ms)^    val leagueChoices = listOf\(.*?^    \)\n')
    s, count = pattern.subn(choices + '\n', s, count=1)
    if count == 0:
        raise SystemExit('leagueChoices block not found; refusing unsafe UI rewrite')

# The UI applies the league filter locally, so the service must remain the
# zero-argument loader. Remove any stale generated call with a filter argument.
s = s.replace('SportsScheduleService.load(leagueFilter)', 'SportsScheduleService.load()')

# If the coverage patch consumed the LazyRow opener, restore it immediately
# before the existing items(leagueChoices) block. Do not touch a valid LazyRow.
if 'items(leagueChoices) { league ->' in s and 'LazyRow(' not in s:
    marker = '        items(leagueChoices) { league ->'
    lazy = '''        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 28.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
'''
    s = s.replace(marker, lazy + marker, 1)

# The specific corruption from patch_schedule_coverage.py leaves a bare
# "        {" immediately before items(). Convert that into the proper LazyRow.
s = s.replace(
    '        {\n            items(leagueChoices) { league ->',
    '''        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 28.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(leagueChoices) { league ->''',
    1,
)

SCREEN.write_text(s, encoding='utf-8')
print('Schedule UI build repair applied: league chips and LazyRow syntax normalized.')
