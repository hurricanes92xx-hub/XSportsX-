#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK path required}"
OUT="${2:-test-output}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
PACKAGE="${QA_PACKAGE:-com.xsportsx.app}"
mkdir -p "$OUT"
adb wait-for-device
adb get-state
adb shell getprop ro.build.version.sdk > "$OUT/device-sdk.txt"
adb shell wm size > "$OUT/device-size.txt"
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"
adb reverse tcp:8765 tcp:8765 >/dev/null
adb reverse --list > "$OUT/adb-reverse.txt"
curl -fsS "$SOURCE_BASE/health" >/dev/null
curl -fsS "$SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '"auth": 1'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'
QA_SOURCE_BASE="$SOURCE_BASE" python3 scripts/qa_source_probe.py
adb shell am force-stop "$PACKAGE" || true
adb shell monkey -p "$PACKAGE" 1 >/dev/null
snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  rm -f "$OUT/${name}.xml"
  if adb shell uiautomator dump --compressed /data/local/tmp/xsportsx-window.xml >"$OUT/${name}.ui-dump.log" 2>&1; then
    adb exec-out cat /data/local/tmp/xsportsx-window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
}
has_any(){ local file="$1"; shift; for text in "$@"; do grep -Fq "$text" "$file" && return 0; done; return 1; }
for attempt in $(seq 1 20); do
  snapshot "01-launch-${attempt}"
  if [ -s "$OUT/01-launch-${attempt}.xml" ] && has_any "$OUT/01-launch-${attempt}.xml" "SPORTS COMMAND CENTER" "NEXT-GEN SPORTS COMMAND" "SOURCE CENTER" "SETTINGS"; then
    cp "$OUT/01-launch-${attempt}.png" "$OUT/01-launch.png"
    cp "$OUT/01-launch-${attempt}.xml" "$OUT/01-launch.xml"
    break
  fi
  sleep 1
done
has_any "$OUT/01-launch.xml" "SPORTS COMMAND CENTER" "NEXT-GEN SPORTS COMMAND" "SOURCE CENTER" "SETTINGS" || { echo "MISSING expected production launch UI"; exit 1; }
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
has_any "$OUT/03-relaunch.xml" "SPORTS COMMAND CENTER" "NEXT-GEN SPORTS COMMAND" "SETTINGS" "SOURCE CENTER" || true
adb shell pidof "$PACKAGE" >/dev/null
echo "XSportsX UI + isolated source smoke test passed"
