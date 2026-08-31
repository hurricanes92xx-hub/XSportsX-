#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="${QA_PACKAGE:-com.xsportsx.app}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
ACTIVITY="$PKG/.MainActivityFuture"
mkdir -p "$OUT"

adb wait-for-device
adb get-state
adb reverse tcp:8765 tcp:8765 >/dev/null
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
# Debug-only deterministic entrypoint. This deliberately bypasses the visual
# home/TV navigation because the source form itself is what this test validates.
adb shell am start -n "$ACTIVITY" --ez QA_OPEN_SOURCE true >/dev/null
sleep 2

snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  rm -f "$OUT/${name}.xml" /tmp/xsportsx-ui-dump.log
  if adb shell uiautomator dump --compressed /data/local/tmp/xsportsx-window.xml >/tmp/xsportsx-ui-dump.log 2>&1; then
    adb exec-out cat /data/local/tmp/xsportsx-window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
  test -s "$OUT/${name}.xml" || cp /tmp/xsportsx-ui-dump.log "$OUT/${name}.ui-dump.log" 2>/dev/null || true
}

bounds_for_id(){
  local file="$1" id="$2"
  python3 - "$file" "$id" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]
for n in root.iter('node'):
    if n.attrib.get('resource-id','') == wanted:
        b=n.attrib.get('bounds','')
        try:
            a,c=b.split(']['); x1,y1=map(int,a.strip('[]').split(',')); x2,y2=map(int,c.strip('[]').split(','))
            print((x1+x2)//2,(y1+y2)//2); raise SystemExit(0)
        except Exception: pass
raise SystemExit(1)
PY
}

exists_id(){
  local file="$1" id="$2"
  python3 - "$file" "$id" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]
raise SystemExit(0 if any(n.attrib.get('resource-id','') == wanted for n in root.iter('node')) else 1)
PY
}

field_text(){
  local file="$1" id="$2"
  python3 - "$file" "$id" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]
for n in root.iter('node'):
    if n.attrib.get('resource-id','') == wanted:
        print(n.attrib.get('text',''))
        raise SystemExit(0)
raise SystemExit(1)
PY
}

click_id(){
  local id="$1" bounds x y
  bounds="$(bounds_for_id "$OUT/source-form.xml" "$id" 2>/dev/null || true)"
  [ -n "$bounds" ] || return 1
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
}

set_field(){
  local id="$1" value="$2" bounds x y observed
  bounds="$(bounds_for_id "$OUT/source-form.xml" "$id" 2>/dev/null || true)"
  [ -n "$bounds" ] || { echo "Missing field resource: $id"; return 1; }
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
  sleep 0.2
  adb shell input keyevent KEYCODE_MOVE_END || true
  for _ in $(seq 1 80); do adb shell input keyevent KEYCODE_DEL || true; done
  adb shell input text "$value"
  sleep 0.5
  snapshot "filled-${id}"
  observed="$(field_text "$OUT/filled-${id}.xml" "$id" 2>/dev/null || true)"
  if [ "$observed" != "$value" ]; then
    echo "Field injection failed for $id"
    echo "Expected: $value"
    echo "Observed: $observed"
    return 1
  fi
}

snapshot "source-form"
for id in source_server source_username source_password source_connect; do
  exists_id "$OUT/source-form.xml" "$id" || { echo "Missing source control: $id"; exit 1; }
done

set_field "source_server" "$SOURCE_BASE"
set_field "source_username" "qauser"
set_field "source_password" "qapass"

adb shell input keyevent KEYCODE_BACK || true
sleep 0.5
snapshot "ready-to-connect"
click_id "source_connect" || { echo "Unable to click source connect action"; exit 1; }

for attempt in $(seq 1 60); do
  sleep 0.25
  snapshot "result-${attempt}"
  XML="$OUT/result-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTION ERROR|Xtream rejected|Connection failed|could not save source|invalid data|did not return a valid' "$XML"; then
    cp "$XML" "$OUT/connection-error.xml"
    cp "$OUT/result-${attempt}.png" "$OUT/connection-error.png"
    echo "Source connection reached an explicit error state"
    exit 1
  fi
  # Successful SourceConnectScreen calls onSaved(), which closes the screen.
  if ! exists_id "$XML" "source_connect"; then
    break
  fi
done

# Re-open the debug source screen and verify that the successfully tested
# credentials were persisted by SourceStore. This makes the test a real
# login/connect/persistence check rather than a button-click smoke test.
adb shell am force-stop "$PKG" || true
adb shell am start -n "$ACTIVITY" --ez QA_OPEN_SOURCE true >/dev/null
sleep 1
snapshot "persisted"
server="$(field_text "$OUT/persisted.xml" "source_server" 2>/dev/null || true)"
user="$(field_text "$OUT/persisted.xml" "source_username" 2>/dev/null || true)"
if [ "$server" != "$SOURCE_BASE" ] || [ "$user" != "qauser" ]; then
  echo "Source connection did not persist verified credentials"
  echo "Observed server: $server"
  echo "Observed username: $user"
  exit 1
fi

echo "Xtream source login/pull/persistence smoke test passed"
exit 0
