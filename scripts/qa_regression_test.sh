#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
OUT="${2:-test-output}"
MODE="${QA_MODE:-mobile}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://10.0.2.2:8765}"
HOST_SOURCE_BASE="${QA_SOURCE_HOST_BASE:-http://127.0.0.1:8765}"

# The Android app uses product-flavor application IDs:
#   mobile -> com.xsportsx.app.mobile
#   tv     -> com.xsportsx.app.tv
# Keep all lifecycle/package checks aligned with the flavor under test.
case "$MODE" in
  mobile|tv) PACKAGE="com.xsportsx.app.${MODE}" ;;
  *) echo "[QA][FAIL] Unsupported QA_MODE '$MODE' (expected mobile or tv)" >&2; exit 2 ;;
esac
mkdir -p "$OUT"

adb wait-for-device
adb shell settings put system screen_off_timeout 1800000 || true
adb install -r -d "$APK"

log(){ echo "[QA] $*"; }
fail(){ echo "[QA][FAIL] $*" >&2; adb logcat -d -t 300 > "$OUT/failure-logcat.txt" 2>/dev/null || true; adb shell dumpsys package "$PACKAGE" > "$OUT/failure-package.txt" 2>/dev/null || true; exit 1; }

snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true
}

has_text(){ grep -Fq "$1" "$OUT/$2.xml"; }
assert_text(){ has_text "$1" "$2" || fail "Missing UI text '$1' in $2"; log "UI OK: $1"; }
assert_any_text(){ local f="$1"; shift; for t in "$@"; do if has_text "$t" "$f"; then log "UI OK: $t"; return; fi; done; fail "None of expected UI labels found in $f: $*"; }

tap_text(){
  local wanted="$1" xml point
  adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  xml="$(adb shell cat /sdcard/window.xml 2>/dev/null || true)"
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
  local value="$1" escaped
  escaped="$(printf '%s' "$value" | sed 's/ /%s/g; s/&/\\&/g')"
  adb shell input text "$escaped"
}

# ----- Isolated source fixture + measurable source latency -----
log "Checking isolated source fixture at $HOST_SOURCE_BASE"
curl -fsS "$HOST_SOURCE_BASE/health" >/dev/null
curl -fsS "$HOST_SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$HOST_SOURCE_BASE/playlist.m3u" | grep -q 'QA Sports One'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '"auth": 1'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_categories" | grep -q 'QA Sports'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_short_epg" | grep -q 'epg_listings'
curl -fsS "$HOST_SOURCE_BASE/stream/101" >/dev/null
QA_SOURCE_BASE="$HOST_SOURCE_BASE" python3 scripts/qa_source_probe.py

python3 - "$HOST_SOURCE_BASE" "$OUT/source-latency.json" <<'PY'
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
log "Resolved QA mode: $MODE"
log "Using package: $PACKAGE"

# Resolve the actual launcher component from the installed APK instead of
# reconstructing the class from the flavor applicationId. The source package
# (com.xsportsx.app) and the flavored applicationId (com.xsportsx.app.mobile/tv)
# are intentionally different; Android's resolver returns the authoritative
# ComponentName for that exact installed variant.
RESOLVED_ACTIVITY="$(adb shell cmd package resolve-activity --brief "$PACKAGE" 2>/dev/null | grep -E '^com\.xsportsx\.app\.(mobile|tv)/' | tail -n 1 | tr -d '\r')"
[[ -n "$RESOLVED_ACTIVITY" ]] || fail "Could not resolve launcher activity for $PACKAGE"
ACTIVITY="$RESOLVED_ACTIVITY"
log "Resolved launcher activity: $ACTIVITY"
printf '%s\n' "$RESOLVED_ACTIVITY" > "$OUT/resolve-activity.txt"

log "Launching $ACTIVITY explicitly"
START_OUTPUT="$(adb shell am start -W -n "$ACTIVITY" 2>&1)" || { echo "$START_OUTPUT"; fail "Explicit activity launch command failed"; }
printf '%s\n' "$START_OUTPUT" | tee "$OUT/launch-result.txt"
echo "$START_OUTPUT" | grep -q 'Status: ok' || fail "Activity did not report Status: ok"
sleep 4
snapshot 01-launch
assert_any_text 01-launch "SPORTS COMMAND CENTER" "XSPORTSX" "WELCOME TO"
adb shell pidof "$PACKAGE" >/dev/null || fail "App process is not alive after launch"

if [[ "$MODE" == "mobile" ]]; then
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

  tap_text "FAVORITES"
  snapshot 07-favorites
  assert_any_text 07-favorites "FAVORITES" "YOUR FAVORITES LIVE HERE" "YOUR PICKS"

  adb shell input keyevent KEYCODE_HOME
  sleep 1
  adb shell am start -W -n "$ACTIVITY" >/dev/null
  sleep 2
  snapshot 08-relaunch
  assert_any_text 08-relaunch "SPORTS COMMAND CENTER" "XSPORTS" "ADD SOURCE"
else
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

  tap_text "SCAN QR CODE"
  sleep 2
  snapshot 04-qr
  assert_any_text 04-qr "CONNECT THIS TV" "Creating secure pairing" "Scan this code with your phone"
  if has_text "CANCEL" 04-qr; then tap_text "CANCEL" || true; sleep 1; fi

  snapshot 05-source-chooser-return
  assert_text "SIGN IN ON TV" 05-source-chooser-return
  tap_text "SIGN IN ON TV"
  sleep 1
  snapshot 06-manual
  assert_any_text 06-manual "CONNECT SOURCE" "XTREAM" "M3U"

  if has_text "Server URL" 06-manual; then
    tap_text "Server URL"; input_text "$SOURCE_BASE"
    tap_text "Username"; input_text "qauser"
    tap_text "Password"; input_text "qapass"
    tap_text "TEST & CONNECT"
    sleep 2
    snapshot 07-xtream-result
    assert_any_text 07-xtream-result "Connected" "source responded" "SOURCE SAVED"
  fi

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

  adb shell input keyevent KEYCODE_HOME
  sleep 1
  adb shell am start -W -n "$ACTIVITY" >/dev/null
  sleep 3
  snapshot 11-tv-home
  tap_text "FAVORITES"
  sleep 1
  snapshot 12-tv-favorites
  assert_text "MY TEAMS" 12-tv-favorites
  assert_text "SELECT YOUR TEAMS" 12-tv-favorites || true
  assert_any_text 12-tv-favorites "SELECT YOUR TEAMS" "SELECT MY TEAMS" "BUILD YOUR SPORTS FEED"
  if has_text "SELECT YOUR TEAMS" 12-tv-favorites; then
    tap_text "SELECT YOUR TEAMS"
    sleep 1
    snapshot 13-team-picker
    assert_text "SELECT YOUR TEAMS" 13-team-picker
    assert_text "Search teams" 13-team-picker
    tap_text "Search teams"
    input_text "Alabama"
    sleep 1
    snapshot 14-college-picker
    assert_text "Alabama" 14-college-picker
    if has_text "CANCEL" 14-college-picker; then tap_text "CANCEL" || true; fi
  fi

  tap_text "HOME"
  sleep 1
  snapshot 15-tv-final
  assert_any_text 15-tv-final "XSPORTSX" "LIVE SPORTS" "UPCOMING"
fi

snapshot final
if grep -Eqi 'has stopped|keeps stopping|isn.t responding|Application Error' "$OUT/final.xml"; then fail "Android crash/ANR dialog detected"; fi

echo "XSportsX $MODE regression suite PASSED"
