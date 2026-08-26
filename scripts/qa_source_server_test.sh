#!/usr/bin/env bash
set -euo pipefail
curl -fsS http://127.0.0.1:8765/health >/dev/null
curl -fsS http://127.0.0.1:8765/playlist.m3u | grep -q '#EXTM3U'
curl -fsS 'http://127.0.0.1:8765/player_api.php?username=qauser&password=qapass' | grep -q '"auth": 1'
curl -fsS 'http://127.0.0.1:8765/player_api.php?username=qauser&password=qapass&action=get_live_streams' | grep -q 'QA Sports One'
python3 scripts/qa_source_probe_v2.py
