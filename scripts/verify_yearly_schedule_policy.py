#!/usr/bin/env python3
import json
from pathlib import Path

policy=json.loads(Path('data/schedule_auto_update_policy.json').read_text())
assert policy['enabled'] is True
assert policy['policy']['annualRollover'] is True
assert policy['policy']['prefetchNextSeason'] is True
assert policy['policy']['neverRequireApkUpdate'] is True
assert policy['policy']['neverBlockPlayback'] is True
source=Path('app/src/main/java/com/xsportsx/app/SportsScheduleService.kt').read_text()
assert 'today.plusDays(370)' in source
assert 'distinctBy' in source
assert 'isLive||it.isUpcoming' in source
print('yearly schedule policy checks passed')
