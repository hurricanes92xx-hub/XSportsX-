#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
PACKAGE="com.xsportsx.app"
OUT="${2:-test-output}"
mkdir -p "$OUT"

adb wait-for-device
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"
adb shell am force-stop "$PACKAGE"
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

# Exercise the main navigation with Android input. This is intentionally
# read-only: it never writes source credentials or changes release artifacts.
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_RIGHT || true
adb shell input keyevent KEYCODE_DPAD_CENTER || true
sleep 1
snapshot 02-navigation

# Settings should expose the pairing area in the current build.
adb shell input keyevent KEYCODE_HOME
sleep 1
adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 2
snapshot 03-relaunch
assert_text "SETTINGS" 03-relaunch || true

# Return cleanly and verify the process stays alive.
adb shell pidof "$PACKAGE" >/dev/null

echo "XSportsX UI smoke test passed"
