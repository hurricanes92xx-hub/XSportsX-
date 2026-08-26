#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="${2:-test-output}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://10.0.2.2:8765}"
PACKAGE="com.xsportsx.app"
mkdir -p "$OUT"

adb wait-for-device
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"

# Verify the emulator can reach the isolated QA provider fixture before touching
# the app. This is deterministic and never uses real provider credentials.
adb shell am force-stop "$PACKAGE" || true
curl -fsS "$SOURCE_BASE/health" >/dev/null
curl -fsS "$SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '"auth": 1'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'

# Also run the same fixture checks from the runner's Python environment.
python3 scripts/qa_source_probe.py

adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 5

snapshot() {
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true
}

assert_text() {
  local text="$1"
  local file="$2"
  grep -Fq "$text" "$OUT/${file}.xml" || {
    echo "MISSING UI TEXT: $text"
    exit 1
  }
}

snapshot 01-launch
assert_text "SPORTS COMMAND CENTER" 01-launch

# Exercise main navigation without modifying source credentials.
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_CENTER || true
sleep 1
snapshot 02-navigation

# Relaunch and verify the process remains healthy.
adb shell input keyevent KEYCODE_HOME
sleep 1
adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 2
snapshot 03-relaunch
assert_text "SETTINGS" 03-relaunch || true
adb shell pidof "$PACKAGE" >/dev/null

echo "XSportsX UI + isolated source smoke test passed"
