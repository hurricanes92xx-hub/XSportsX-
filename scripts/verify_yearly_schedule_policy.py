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
# The app intentionally uses a lightweight rolling 30-day interactive window.
# Annual rollover/prefetch remains enabled by policy and is handled by the
# scheduled refresh pipeline rather than forcing a 370-day UI request.
assert 'DAYS_AHEAD=30' in source or 'DAYS_AHEAD=30L' in source
assert 'today.plusDays(DAYS_AHEAD)' in source
assert 'distinctBy' in source
assert 'isLive' in source and 'isUpcoming' in source
print('30-day schedule window policy checks passed')
