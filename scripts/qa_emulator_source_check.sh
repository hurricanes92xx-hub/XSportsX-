#!/usr/bin/env bash
set -euo pipefail
# This runs inside the emulator. 10.0.2.2 maps to the GitHub runner host.
adb shell 'command -v wget >/dev/null 2>&1 && wget -qO- http://10.0.2.2:8765/health || true' | grep -q '"ok": true'
adb shell 'command -v wget >/dev/null 2>&1 && wget -qO- "http://10.0.2.2:8765/player_api.php?username=qauser&password=qapass&action=get_live_streams" || true' | grep -q 'QA Sports One'
adb shell 'command -v wget >/dev/null 2>&1 && wget -qO- http://10.0.2.2:8765/playlist.m3u || true' | grep -q '#EXTM3U'
echo "Emulator-to-QA-source network path passed"
