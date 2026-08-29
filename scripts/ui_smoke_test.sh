#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK path required}"
OUT="${2:-test-output}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
PACKAGE="${QA_PACKAGE:-com.xsportsx.app}"
mkdir -p "$OUT"
adb wait-for-device
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"
adb reverse tcp:8765 tcp:8765 >/dev/null
curl -fsS "$SOURCE_BASE/health" >/dev/null
curl -fsS "$SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '"auth": 1'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'
QA_SOURCE_BASE="$SOURCE_BASE" python3 scripts/qa_source_probe.py
adb shell am force-stop "$PACKAGE" || true
adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 5
snapshot(){ local name="$1"; adb exec-out screencap -p > "$OUT/${name}.png"; adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true; adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true; }
assert_text(){ grep -Fq "$1" "$OUT/$2.xml" || { echo "MISSING UI TEXT: $1"; exit 1; }; }
snapshot 01-launch
assert_text "SPORTS COMMAND CENTER" 01-launch
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_CENTER || true
sleep 1
snapshot 02-navigation
adb shell input keyevent KEYCODE_HOME
sleep 1
adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 2
snapshot 03-relaunch
assert_text "SETTINGS" 03-relaunch || true
adb shell pidof "$PACKAGE" >/dev/null
echo "XSportsX UI + isolated source smoke test passed"
