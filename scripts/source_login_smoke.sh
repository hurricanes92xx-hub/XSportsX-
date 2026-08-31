#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="${QA_PACKAGE:-com.xsportsx.app}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
mkdir -p "$OUT"

adb wait-for-device
adb get-state
adb reverse tcp:8765 tcp:8765 >/dev/null
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
adb shell monkey -p "$PKG" 1 >/dev/null
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

click_id(){
  local id="$1" bounds x y
  snapshot "probe-${id}"
  bounds="$(bounds_for_id "$OUT/probe-${id}.xml" "$id" 2>/dev/null || true)"
  [ -n "$bounds" ] || return 1
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
  return 0
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

set_field(){
  local id="$1" value="$2" bounds x y observed
  for _ in $(seq 1 10); do
    snapshot "field-${id}"
    bounds="$(bounds_for_id "$OUT/field-${id}.xml" "$id" 2>/dev/null || true)"
    [ -n "$bounds" ] && break
    sleep 0.5
  done
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

# The production Compose hierarchy now exposes stable resource IDs through
# testTagsAsResourceId. This avoids guessing from labels, merged semantics,
# keyboard focus, or screen coordinates. It is the Android-recommended bridge
# for UIAutomator to interact with Compose nodes.
for attempt in $(seq 1 15); do
  snapshot "nav-${attempt}"
  if exists_id "$OUT/nav-${attempt}.xml" "source_server"; then
    break
  fi
  if click_id "nav_sources"; then
    sleep 1
  else
    sleep 0.5
  fi
done

snapshot "source-form"
exists_id "$OUT/source-form.xml" "source_server" || { echo "Missing source server field"; exit 1; }
exists_id "$OUT/source-form.xml" "source_username" || { echo "Missing source username field"; exit 1; }
exists_id "$OUT/source-form.xml" "source_password" || { echo "Missing source password field"; exit 1; }
exists_id "$OUT/source-form.xml" "source_connect" || { echo "Missing source connect action"; exit 1; }

set_field "source_server" "$SOURCE_BASE"
set_field "source_username" "qauser"
set_field "source_password" "qapass"

# Keep the keyboard out of the way before invoking the real connection action.
adb shell input keyevent KEYCODE_BACK || true
sleep 0.5
click_id "source_connect" || { echo "Unable to click source connect action"; exit 1; }

for attempt in $(seq 1 40); do
  sleep 0.25
  snapshot "result-${attempt}"
  XML="$OUT/result-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTION ERROR|Connection failed|invalid data|did not return a valid' "$XML"; then
    cp "$XML" "$OUT/connection-error.xml"
    cp "$OUT/result-${attempt}.png" "$OUT/connection-error.png"
    echo "Source connection reached an explicit error state"
    exit 1
  fi
  if grep -Eqi 'SOURCE SAVED|SOURCE CONNECTED|Connection successful' "$XML" || exists_id "$XML" "source_saved" 2>/dev/null; then
    cp "$XML" "$OUT/connected.xml"
    cp "$OUT/result-${attempt}.png" "$OUT/connected.png"
    echo "Xtream source login/pull smoke test passed"
    exit 0
  fi
done

echo "Source connection did not reach a success state"
exit 1
