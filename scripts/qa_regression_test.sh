#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK path required}"
OUT="${2:-test-output}"
MODE="${QA_MODE:-mobile}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://10.0.2.2:8765}"
HOST_SOURCE_BASE="${QA_SOURCE_HOST_BASE:-http://127.0.0.1:8765}"
case "$MODE" in mobile|tv) PACKAGE="com.xsportsx.app.${MODE}";; *) echo "[QA][FAIL] Unsupported QA_MODE '$MODE'" >&2; exit 2;; esac
mkdir -p "$OUT"
log(){ echo "[QA] $*"; }
fail(){ echo "[QA][FAIL] $*" >&2; adb logcat -d -t 300 > "$OUT/failure-logcat.txt" 2>/dev/null || true; adb shell dumpsys package "$PACKAGE" > "$OUT/failure-package.txt" 2>/dev/null || true; exit 1; }
snapshot(){ local name="$1"; adb exec-out screencap -p > "$OUT/${name}.png"; adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true; adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true; }
refresh_ui(){ local name="$1"; adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true; adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" || true; }
has_text(){ grep -Fiq -- "$1" "$OUT/$2.xml"; }
assert_text(){ has_text "$1" "$2" || fail "Missing UI text '$1' in $2"; log "UI OK: $1"; }
assert_any_text(){ local f="$1"; shift; for t in "$@"; do if has_text "$t" "$f"; then log "UI OK: $t"; return; fi; done; fail "None of expected UI labels found in $f: $*"; }
ui_has_any(){ local f="$1"; shift; for t in "$@"; do has_text "$t" "$f" && return 0; done; return 1; }
tap_text(){ local wanted="$1" xml point; refresh_ui __tap; xml="$(cat "$OUT/__tap.xml" 2>/dev/null || true)"; point="$(python3 - "$wanted" "$xml" <<'PY'
import re,sys,html
wanted=sys.argv[1]; xml=html.unescape(sys.argv[2])
for attr in ('text','content-desc'):
 p=r'<node[^>]*'+attr+r'="'+re.escape(wanted)+r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'; m=re.search(p,xml,re.I)
 if m:
  x1,y1,x2,y2=map(int,m.groups()); print((x1+x2)//2,(y1+y2)//2); break
else: print('NOT_FOUND')
PY
)"; [[ "$point" != "NOT_FOUND" ]] || fail "Could not locate UI target '$wanted'"; adb shell input tap ${point% *} ${point#* }; sleep 1; }
tap_any_text(){ local xml wanted point; refresh_ui __tap_any; xml="$(cat "$OUT/__tap_any.xml" 2>/dev/null || true)"; for wanted in "$@"; do point="$(python3 - "$wanted" "$xml" <<'PY'
import re,sys,html
wanted=sys.argv[1]; xml=html.unescape(sys.argv[2])
for attr in ('text','content-desc'):
 p=r'<node[^>]*'+attr+r'="'+re.escape(wanted)+r'"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'; m=re.search(p,xml,re.I)
 if m:
  x1,y1,x2,y2=map(int,m.groups()); print((x1+x2)//2,(y1+y2)//2); break
else: print('NOT_FOUND')
PY
)"; if [[ "$point" != "NOT_FOUND" ]]; then log "Tapping available UI target '$wanted'"; adb shell input tap ${point% *} ${point#* }; sleep 1; return 0; fi; done; return 1; }
input_text(){ local value="$1" escaped; escaped="$(printf '%s' "$value" | sed 's/ /%s/g; s/&/\\&/g')"; adb shell input text "$escaped"; }
fill_source_credentials(){
  local base="$1"
  tap_text "Server URL"; input_text "$base"; adb shell input keyevent KEYCODE_BACK || true; sleep 1
  tap_text "Username"; input_text "qauser"; adb shell input keyevent KEYCODE_BACK || true; sleep 1
  tap_text "Password"; input_text "qapass"; adb shell input keyevent KEYCODE_BACK || true; sleep 1
}

log "Checking isolated source fixture at $HOST_SOURCE_BASE"
curl -fsS "$HOST_SOURCE_BASE/health" >/dev/null
curl -fsS "$HOST_SOURCE_BASE/playlist.m3u" | grep -q '#EXTM3U'
curl -fsS "$HOST_SOURCE_BASE/playlist.m3u" | grep -q 'QA Sports One'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass" | grep -q '\"auth\": 1'
curl -fsS "$HOST_SOURCE_BASE/player_api.php?username=qauser&password=qapass&action=get_live_streams" | grep -q 'QA Sports One'
QA_SOURCE_BASE="$HOST_SOURCE_BASE" python3 scripts/qa_source_probe.py

python3 - "$HOST_SOURCE_BASE" "$OUT/source-latency.json" <<'PY'
import json,sys,time,urllib.request
base=sys.argv[1]; out=sys.argv[2]
paths=['/health','/playlist.m3u','/player_api.php?username=qauser&password=qapass','/player_api.php?username=qauser&password=qapass&action=get_live_streams']
rows=[]
for path in paths:
 t=time.perf_counter(); data=urllib.request.urlopen(base+path,timeout=10).read(); rows.append({'path':path,'elapsed_ms':round((time.perf_counter()-t)*1000,2),'bytes':len(data)})
json.dump({'fixture':'xsportsx-qa','checks':rows},open(out,'w'),indent=2); print(json.dumps(rows,indent=2))
PY

adb shell am force-stop "$PACKAGE" || true
log "Resolved QA mode: $MODE"
log "Using package: $PACKAGE"
RESOLVE_RAW="$(adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER "$PACKAGE" 2>/dev/null || true)"
ACTIVITY="$(printf '%s\n' "$RESOLVE_RAW" | sed 's/\r$//' | grep -E '^com\.xsportsx\.app\.(mobile|tv)/' | tail -n 1 || true)"
[[ -n "$ACTIVITY" ]] || fail "Could not resolve launcher activity for $PACKAGE (raw: $RESOLVE_RAW)"
log "Resolved launcher activity: $ACTIVITY"
printf '%s\n' "$ACTIVITY" > "$OUT/resolve-activity.txt"
START_OUTPUT="$(adb shell am start -W -n "$ACTIVITY" 2>&1)" || { echo "$START_OUTPUT"; fail "Explicit activity launch command failed"; }
printf '%s\n' "$START_OUTPUT" | tee "$OUT/launch-result.txt"
printf '%s\n' "$START_OUTPUT" | tr -d '\r' | grep -Eq 'Status:[[:space:]]*ok([[:space:]]|$)' || fail "Activity did not report Status: ok"
sleep 4
snapshot 01-launch
assert_any_text 01-launch "SPORTS COMMAND CENTER" "NEXT-GEN SPORTS COMMAND" "XSPORTSX" "WELCOME TO" "ADD SOURCE"
adb shell pidof "$PACKAGE" >/dev/null || fail "App process is not alive after launch"

if [[ "$MODE" == "mobile" ]]; then
  tap_text "LIVE"
  log "Waiting for Live feed to settle"
  live_ok=0
  for attempt in $(seq 1 20); do snapshot "02-live-${attempt}"; if ui_has_any "02-live-${attempt}" "LIVE NOW" "No games live right now" "LIVE SPORTS"; then log "Live feed ready after ${attempt}s"; cp "$OUT/02-live-${attempt}.png" "$OUT/02-live.png"; cp "$OUT/02-live-${attempt}.xml" "$OUT/02-live.xml"; live_ok=1; break; fi; log "Live feed still settling (${attempt}/20)"; sleep 1; done
  [[ "$live_ok" -eq 1 ]] || fail "Live feed did not expose an expected settled UI state within 20s"
  tap_text "NETWORKS"; snapshot 03-networks; assert_text "NETWORKS" 03-networks
  tap_text "FAVORITES"; snapshot 04-favorites; assert_text "FAVORITES" 04-favorites; assert_any_text 04-favorites "YOUR PICKS" "YOUR FAVORITES LIVE HERE"
  tap_text "HOME"; snapshot 05-home; assert_any_text 05-home "XSPORTS" "NEXT-GEN SPORTS COMMAND"
  tap_any_text "ADD SOURCE" "CONNECT NOW →" "CONNECT SOURCE →" || fail "Could not locate mobile source entry point"
  sleep 1; snapshot 06-source; assert_any_text 06-source "CONNECT SOURCE" "XTREAM" "M3U" "Server URL"
  if has_text "Server URL" 06-source; then
    fill_source_credentials "$SOURCE_BASE"
    refresh_ui 07-source-ready; assert_any_text 07-source-ready "TEST & CONNECT" "TESTING SOURCE" "CONNECT SOURCE"
    tap_any_text "TEST & CONNECT" "CONNECT SOURCE" || fail "Could not locate mobile source connect action"
    sleep 2; snapshot 08-source-connected; assert_any_text 08-source-connected "Connected" "source responded" "SOURCE SAVED" "Connection successful"
  else fail "Source connection form did not expose Server URL"; fi
  adb shell input keyevent KEYCODE_HOME; sleep 1; adb shell am start -W -n "$ACTIVITY" >/dev/null; sleep 2; snapshot 09-relaunch; assert_any_text 09-relaunch "SPORTS COMMAND CENTER" "NEXT-GEN SPORTS COMMAND" "XSPORTS" "ADD SOURCE" "SOURCE READY"
else
  tap_text "SETTINGS"; snapshot 02-tv-settings; assert_text "SETTINGS" 02-tv-settings; assert_any_text 02-tv-settings "OPEN CONNECTION SETTINGS" "CONNECT YOUR SOURCE"
  tap_any_text "OPEN CONNECTION SETTINGS" "CONNECT YOUR SOURCE" || true; sleep 1
  snapshot 03-source-chooser; assert_text "CONNECT YOUR SOURCE" 03-source-chooser; assert_text "SCAN QR CODE" 03-source-chooser; assert_any_text 03-source-chooser "SIGN IN ON TV" "MANUAL" "XTREAM" "M3U"
  tap_text "SCAN QR CODE"; sleep 2; snapshot 04-qr; assert_any_text 04-qr "CONNECT THIS TV" "Creating secure pairing" "Scan this code with your phone"
  if has_text "CANCEL" 04-qr; then tap_text "CANCEL"; else adb shell input keyevent KEYCODE_BACK; fi
  sleep 1; snapshot 05-after-qr
  if ! ui_has_any 05-after-qr "CONNECT YOUR SOURCE" "SCAN QR CODE"; then
    log "Recovering TV navigation after QR cancellation"
    for n in 1 2 3; do snapshot "05-recover-$n"; if ui_has_any "05-recover-$n" "CONNECT YOUR SOURCE" "SCAN QR CODE"; then break; fi; tap_any_text "OPEN CONNECTION SETTINGS" "CONNECTION SETTINGS" "SETTINGS" "TV SETTINGS" || adb shell input keyevent KEYCODE_BACK; sleep 1; done
  fi
  snapshot 06-source-chooser-return; if ! ui_has_any 06-source-chooser-return "CONNECT YOUR SOURCE" "SCAN QR CODE"; then tap_any_text "OPEN CONNECTION SETTINGS" "CONNECTION SETTINGS" || fail "Source chooser unavailable after QR cancellation recovery"; sleep 1; snapshot 06-source-chooser-return; fi
  assert_text "CONNECT YOUR SOURCE" 06-source-chooser-return; assert_text "SCAN QR CODE" 06-source-chooser-return; assert_any_text 06-source-chooser-return "SIGN IN ON TV" "MANUAL" "XTREAM" "M3U"
  tap_any_text "SIGN IN ON TV" "MANUAL" "XTREAM" "M3U" || fail "Could not open TV manual source form"
  sleep 1; snapshot 07-manual; assert_any_text 07-manual "CONNECT SOURCE" "XTREAM" "M3U" "Server URL" "SIGN IN"
  if has_text "Server URL" 07-manual; then
    fill_source_credentials "$SOURCE_BASE"
    refresh_ui 07-manual-ready; assert_any_text 07-manual-ready "TEST & CONNECT" "TESTING SOURCE" "CONNECT SOURCE"
    tap_any_text "TEST & CONNECT" "CONNECT SOURCE" || fail "Could not locate TV source connect action"
    sleep 2; snapshot 08-xtream-result; assert_any_text 08-xtream-result "Connected" "source responded" "SOURCE SAVED" "Connection successful"
  else fail "TV manual source form did not expose Server URL"; fi
  snapshot 09-manual-m3u; tap_text "M3U"; sleep 1; snapshot 10-m3u; assert_any_text 10-m3u "M3U playlist URL" "M3U"
  if has_text "M3U playlist URL" 10-m3u; then
    tap_text "M3U playlist URL"; input_text "$SOURCE_BASE/playlist.m3u"; refresh_ui 10-m3u-ready; assert_any_text 10-m3u-ready "TEST & CONNECT" "TESTING SOURCE" "CONNECT SOURCE"; tap_any_text "TEST & CONNECT" "CONNECT SOURCE" || fail "Could not locate TV M3U connect action"; sleep 2; snapshot 11-m3u-result; assert_any_text 11-m3u-result "Connected" "source responded" "SOURCE SAVED" "Connection successful"
  else fail "TV M3U form did not expose playlist URL"; fi
  adb shell input keyevent KEYCODE_HOME; sleep 1; adb shell am start -W -n "$ACTIVITY" >/dev/null; sleep 3; snapshot 12-tv-home; tap_text "FAVORITES"; sleep 1; snapshot 13-tv-favorites; assert_text "MY TEAMS" 13-tv-favorites; assert_any_text 13-tv-favorites "SELECT YOUR TEAMS" "SELECT MY TEAMS" "BUILD YOUR SPORTS FEED"
  if has_text "SELECT YOUR TEAMS" 13-tv-favorites; then tap_text "SELECT YOUR TEAMS"; sleep 1; snapshot 14-team-picker; assert_text "SELECT YOUR TEAMS" 14-team-picker; assert_text "Search teams" 14-team-picker; tap_text "Search teams"; input_text "Alabama"; sleep 1; snapshot 15-college-picker; assert_text "Alabama" 15-college-picker; if has_text "CANCEL" 15-college-picker; then tap_text "CANCEL" || true; fi; fi
  tap_text "HOME"; sleep 1; snapshot 16-tv-final; assert_any_text 16-tv-final "XSPORTSX" "LIVE SPORTS" "UPCOMING"
fi
snapshot final
if grep -Eqi 'has stopped|keeps stopping|isn.t responding|Application Error' "$OUT/final.xml"; then fail "Android crash/ANR dialog detected"; fi
echo "XSportsX $MODE regression suite PASSED"
