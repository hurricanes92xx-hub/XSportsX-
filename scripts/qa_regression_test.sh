#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="${2:-test-output}"
MODE="${QA_MODE:-mobile}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://10.0.2.2:8765}"
PACKAGE="com.xsportsx.app"
mkdir -p "$OUT"

adb wait-for-device
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"

log(){ echo "[QA] $*"; }
fail(){ echo "[QA][FAIL] $*" >&2; exit 1; }

snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true
}

has_text(){
  local text="$1"
  local file="$2"
  grep -Fq "$text" "$OUT/${file}.xml"
}

assert_text(){
  local text="$1"
  local file="$2"
  has_text "$text" "$file" || fail "Missing UI text '$text' in $file"
  log "UI OK: $text"
}

assert_any_text(){
  local file="$1"; shift
  local text
  for text in "$@"; do
    if has_text "$text" "$file"; then log "UI OK: $text"; return 0; fi
  done
  fail "None of expected UI labels found in $file: $*"
}

# Find a Compose/UIAutomator node by visible text/content-desc and tap its center.
tap_text(){
  local wanted="$1"
  local xml
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  xml="$(adb shell cat /sdcard/window.xml 2>/dev/null || true)"
  python3 - "$wanted" "$xml" <<'PY'
import re,sys,html
wanted=sys.argv[1]
xml=html.unescape(sys.argv[2])
# Prefer exact text, then exact content-desc.
patterns=[
    r'<node[^>]*(?:text|content-desc)="'+re.escape(wanted)+r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
]
for p in patterns:
    m=re.search(p,xml)
    if m:
        x1,y1,x2,y2=map(int,m.groups()); print((x1+x2)//2,(y1+y2)//2); sys.exit(0)
print('NOT_FOUND')
PY
  local point
  point="$(python3 - "$wanted" "$xml" <<'PY'
import re,sys,html
wanted=sys.argv[1]; xml=html.unescape(sys.argv[2])
for attr in ('text','content-desc'):
    p=r'<node[^>]*'+attr+r'="'+re.escape(wanted)+r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    m=re.search(p,xml)
    if m:
        x1,y1,x2,y2=map(int,m.groups()); print((x1+x2)//2,(y1+y2)//2); break
else: print('NOT_FOUND')
PY
)"
  [[ "$point" != "NOT_FOUND" ]] || fail "Could not locate UI target '$wanted'"
  adb shell input tap ${point% *} ${point#* }
  sleep 1
}

input_text(){
  local value="$1"
  local escaped
  escaped="$(printf '%s' "$value" | sed 's/ /%s/g; s/&/\\&/g')"
  adb shell input text "$escaped"
}

# ----- Source fixture and latency checks -----
log "Checking isolated source fixture"
curl -fsS "$SOURCE_BASE/health" >/dev/null
curl -fsS "$SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$SOURCE_BASE/playlist.m3u" | grep -q 'QA Sports One'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '"auth": 1'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_categories" | grep -q 'QA Sports'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'
curl -fsS "$SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_short_epg" | grep -q 'epg_listings'
curl -fsS "$SOURCE_BASE/stream/101" >/dev/null
python3 scripts/qa_source_probe.py

# Measure deterministic fixture timing so regressions in source access are visible.
python3 - "$SOURCE_BASE" "$OUT/source-latency.json" <<'PY'
import json,sys,time,urllib.request
base=sys.argv[1]; out=sys.argv[2]
paths=['/health','/playlist.m3u','/player_api.php?username=qauser&password=qapass','/player_api.php?username=qauser&password=qapass&action=get_live_streams']
rows=[]
for path in paths:
    t=time.perf_counter(); data=urllib.request.urlopen(base+path,timeout=10).read(); elapsed=(time.perf_counter()-t)*1000
    rows.append({'path':path,'elapsed_ms':round(elapsed,2),'bytes':len(data)})
json.dump({'fixture':'xsportsx-qa','checks':rows},open(out,'w'),indent=2)
print(json.dumps(rows,indent=2))
PY

# ----- App lifecycle -----
adb shell am force-stop "$PACKAGE" || true
adb shell monkey -p "$PACKAGE" 1 >/dev/null
sleep 4
snapshot 01-launch
assert_any_text 01-launch "SPORTS COMMAND CENTER" "XSPORTSX" "WELCOME TO"
adb shell pidof "$PACKAGE" >/dev/null || fail "App process is not alive after launch"

if [[ "$MODE" == "mobile" ]]; then
  # Main navigation and sport filters.
  tap_text "LIVE"
  snapshot 02-live
  assert_any_text 02-live "LIVE NOW" "No games live right now" "LIVE SPORTS"

  tap_text "SEARCH"
  snapshot 03-search
  assert_text "SEARCH SPORTS" 03-search
  assert_text "Find teams, fighters, leagues and events" 03-search

  tap_text "SOURCES"
  snapshot 04-sources
  assert_any_text 04-sources "SOURCE CENTER" "CONNECT SOURCE"
  assert_any_text 04-sources "XTREAM CODES" "CONNECT SOURCE"

  # Exercise real Xtream connection against the isolated fixture.
  tap_text "Server URL"
  input_text "$SOURCE_BASE"
  tap_text "Username"
  input_text "qauser"
  tap_text "Password"
  input_text "qapass"
  snapshot 05-source-filled
  tap_text "CONNECT SOURCE"
  sleep 2
  snapshot 06-source-connected
  assert_any_text 06-source-connected "SOURCE SAVED" "Connected" "source responded"

  # Verify relaunch keeps the app healthy after source configuration.
  adb shell input keyevent KEYCODE_HOME
  sleep 1
  adb shell monkey -p "$PACKAGE" 1 >/dev/null
  sleep 2
  snapshot 07-relaunch
  assert_any_text 07-relaunch "SPORTS COMMAND CENTER" "XSPORTSX"
else
  # TV navigation, focusable controls and connection chooser.
  tap_text "SETTINGS"
  snapshot 02-tv-settings
  assert_text "SETTINGS" 02-tv-settings
  assert_any_text 02-tv-settings "OPEN CONNECTION SETTINGS" "CONNECT YOUR SOURCE"

  if has_text "OPEN CONNECTION SETTINGS" 02-tv-settings; then
    tap_text "OPEN CONNECTION SETTINGS"
    sleep 1
  fi
  snapshot 03-source-chooser
  assert_text "CONNECT YOUR SOURCE" 03-source-chooser
  assert_text "SCAN QR CODE" 03-source-chooser
  assert_text "SIGN IN ON TV" 03-source-chooser

  # QR flow: verify the QR screen can be opened without injecting credentials.
  tap_text "SCAN QR CODE"
  sleep 2
  snapshot 04-qr
  assert_any_text 04-qr "CONNECT THIS TV" "Creating secure pairing" "Scan this code with your phone"
  if has_text "CANCEL" 04-qr; then tap_text "CANCEL" || true; sleep 1; fi

  # Manual Xtream flow.
  snapshot 05-source-chooser-return
  assert_text "SIGN IN ON TV" 05-source-chooser-return
  tap_text "SIGN IN ON TV"
  sleep 1
  snapshot 06-manual
  assert_any_text 06-manual "CONNECT SOURCE" "XTREAM" "M3U"

  # Try Xtream credentials first.
  if has_text "Server URL" 06-manual; then
    tap_text "Server URL"; input_text "$SOURCE_BASE"
    tap_text "Username"; input_text "qauser"
    tap_text "Password"; input_text "qapass"
    tap_text "TEST & CONNECT"
    sleep 2
    snapshot 07-xtream-result
    assert_any_text 07-xtream-result "Connected" "source responded" "SOURCE SAVED"
  fi

  # Verify M3U mode is present and accepts the deterministic playlist URL.
  snapshot 08-manual-m3u
  if has_text "M3U" 08-manual-m3u; then
    tap_text "M3U"
    sleep 1
    snapshot 09-m3u
    assert_any_text 09-m3u "M3U playlist URL" "M3U"
    if has_text "M3U playlist URL" 09-m3u; then
      tap_text "M3U playlist URL"
      input_text "$SOURCE_BASE/playlist.m3u"
      tap_text "TEST & CONNECT"
      sleep 2
      snapshot 10-m3u-result
      assert_any_text 10-m3u-result "Connected" "source responded" "SOURCE SAVED"
    fi
  fi

  # TV relaunch/lifecycle.
  adb shell input keyevent KEYCODE_HOME
  sleep 1
  adb shell monkey -p "$PACKAGE" 1 >/dev/null
  sleep 3
  snapshot 11-tv-relaunch
  assert_any_text 11-tv-relaunch "XSPORTSX" "WELCOME TO" "LIVE SPORTS"
fi

# Capture a final UI hierarchy for debugging and confirm no crash dialog is present.
snapshot final
if grep -Eqi 'has stopped|keeps stopping|isn.t responding|Application Error' "$OUT/final.xml"; then
  fail "Android crash/ANR dialog detected"
fi

echo "XSportsX $MODE regression suite PASSED"
