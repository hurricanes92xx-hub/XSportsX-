#!/usr/bin/env python3
import json, urllib.request
BASE='http://127.0.0.1:8765'
def get(p): return urllib.request.urlopen(BASE+p,timeout=10).read().decode()
assert json.loads(get('/health'))['ok'] is True
assert 'QA Sports One' in get('/playlist.m3u')
assert '"auth": 1' in get('/player_api.php?username=qauser&password=qapass')
assert 'QA Sports One' in get('/player_api.php?username=qauser&password=qapass&action=get_live_streams')
print('QA fixture OK')
