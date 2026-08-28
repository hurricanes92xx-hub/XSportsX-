#!/usr/bin/env python3
import json
import re
from pathlib import Path

policy=json.loads(Path('data/schedule_auto_update_policy.json').read_text())
assert policy['enabled'] is True
assert policy['policy']['annualRollover'] is True
assert policy['policy']['prefetchNextSeason'] is True
assert policy['policy']['neverRequireApkUpdate'] is True
assert policy['policy']['neverBlockPlayback'] is True
source=Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt').read_text()
# The APK uses a lightweight rolling 7-day interactive window. The separate
# schedule generator can retain a much broader season-aware feed; the device
# should not fetch/render that entire catalog for the interactive screen.
assert re.search(r'\bDAYS_AHEAD\s*=\s*7(?:L)?\b', source)
assert re.search(r'\bMAX_GAMES_PER_LEAGUE\s*=\s*75\b', source)
assert re.search(r'today\.plusDays\(\s*DAYS_AHEAD(?:\.toLong\(\))?\s*\)', source)
assert 'distinctBy' in source
assert 'isLive' in source and 'isUpcoming' in source
print('7-day interactive schedule window policy checks passed')
