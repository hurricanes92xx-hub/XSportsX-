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
# The app intentionally uses a lightweight rolling 30-day interactive window.
# Allow normal Kotlin formatting and an explicit Long conversion.
assert re.search(r'\bDAYS_AHEAD\s*=\s*30(?:L)?\b', source)
assert re.search(r'today\.plusDays\(\s*DAYS_AHEAD(?:\.toLong\(\))?\s*\)', source)
assert 'distinctBy' in source
assert 'isLive' in source and 'isUpcoming' in source
print('30-day schedule window policy checks passed')
