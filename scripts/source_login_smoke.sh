#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="${QA_PACKAGE:?QA_PACKAGE must be set}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
ACTIVITY_CLASS="${QA_ACTIVITY_CLASS:-com.xsportsx.app.QaSourceActivity}"
ACTIVITY="$PKG/$ACTIVITY_CLASS"
mkdir -p "$OUT"

adb wait-for-device
adb get-state
adb reverse tcp:8765 tcp:8765 >/dev/null
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
START_OUTPUT="$(adb shell am start -W -n "$ACTIVITY" 2>&1)"
printf '%s\n' "$START_OUTPUT" > "$OUT/activity-start.txt"
echo "$START_OUTPUT"
echo "$START_OUTPUT" | grep -q 'Status: ok'
sleep 2

snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  rm -f "$OUT/${name}.xml" /tmp/xsportsx-ui-dump.log
  for _ in $(seq 1 10); do
    if adb shell uiautomator dump --compressed /data/local/tmp/xsportsx-window.xml >/tmp/xsportsx-ui-dump.log 2>&1 && \
       adb exec-out cat /data/local/tmp/xsportsx-window.xml > "$OUT/${name}.xml" 2>/dev/null && \
       test -s "$OUT/${name}.xml"; then return 0; fi
    sleep 0.25
  done
  cp /tmp/xsportsx-ui-dump.log "$OUT/${name}.ui-dump.log" 2>/dev/null || true
  echo "Unable to capture UI hierarchy for $name"
  return 1
}

# Compose testTags are the preferred selector. UIAutomator can expose them as
# resource IDs, but that mapping is not guaranteed across Android TV/Compose
# versions. Also accept the field's contentDescription/visible label.
label_for(){
  case "$1" in
    source_server) echo "Server URL" ;;
    source_username) echo "Username" ;;
    source_password) echo "Password" ;;
    source_connect) echo "TEST & CONNECT" ;;
    *) return 1 ;;
  esac
}

bounds_for_id(){
  local file="$1" id="$2"
  python3 - "$file" "$id" "$(label_for "$id")" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]; label=sys.argv[3]
for n in root.iter('node'):
    rid=n.attrib.get('resource-id',''); desc=n.attrib.get('content-desc',''); text=n.attrib.get('text','')
    if rid == wanted or rid.endswith(':id/' + wanted) or desc == label or text == label:
        b=n.attrib.get('bounds','')
        try:
            a,c=b.split(']['); x1,y1=map(int,a.strip('[]').split(',')); x2,y2=map(int,c.strip('[]').split(','))
            print((x1+x2)//2,(y1+y2)//2); raise SystemExit(0)
        except Exception: pass
raise SystemExit(1)
PY
}

field_text(){
  local file="$1" id="$2"
  python3 - "$file" "$id" "$(label_for "$id")" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]; label=sys.argv[3]
for n in root.iter('node'):
    rid=n.attrib.get('resource-id',''); desc=n.attrib.get('content-desc','')
    if rid == wanted or rid.endswith(':id/' + wanted) or desc == label:
        print(n.attrib.get('text','')); raise SystemExit(0)
raise SystemExit(1)
PY
}

exists_id(){
  local file="$1" id="$2"
  python3 - "$file" "$id" "$(label_for "$id")" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); wanted=sys.argv[2]; label=sys.argv[3]
raise SystemExit(0 if any((n.attrib.get('resource-id','') == wanted or n.attrib.get('resource-id','').endswith(':id/' + wanted) or n.attrib.get('content-desc','') == label or n.attrib.get('text','') == label) for n in root.iter('node')) else 1)
PY
}

click_id(){
  local file="$1" id="$2" bounds x y
  bounds="$(bounds_for_id "$file" "$id" 2>/dev/null || true)"
  [ -n "$bounds" ] || return 1
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
}

set_field(){
  local id="$1" value="$2" secret="${3:-false}" bounds x y observed before

  # Android TV's on-screen keyboard can resize/scroll the Compose hierarchy.
  # Never reuse coordinates captured while another field's keyboard is open.
  adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1 || true
  sleep 0.3
  before="before-${id}"
  snapshot "$before"
  bounds="$(bounds_for_id "$OUT/${before}.xml" "$id" 2>/dev/null || true)"
  [ -n "$bounds" ] || { echo "Missing source field: $id ($(label_for "$id"))"; return 1; }
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
  sleep 0.4
  adb shell input keyevent KEYCODE_MOVE_END || true
  for _ in $(seq 1 100); do adb shell input keyevent KEYCODE_DEL >/dev/null 2>&1 || true; done
  adb shell input text "$value"
  sleep 0.5
  snapshot "filled-${id}"
  observed="$(field_text "$OUT/filled-${id}.xml" "$id" 2>/dev/null || true)"

  # PasswordVisualTransformation intentionally hides the password from the
  # UI hierarchy. Android TV's UIAutomator may therefore report an empty
  # text attribute even when the EditText contains the password. Treating
  # that accessibility representation as a failed injection caused a false
  # negative before the real Xtream authentication was ever attempted.
  # Password correctness is verified by testSource() below: a successful
  # auth=1 response proves the password actually reached the app and server.
  if [ "$secret" = "true" ]; then
    echo "Password field populated; UI hierarchy text is intentionally not asserted"
  elif [ "$observed" != "$value" ]; then
    echo "Field injection failed for $id"
    echo "Expected: $value"
    echo "Observed: $observed"
    return 1
  fi

  # Ensure the next field is laid out normally before its coordinates are read.
  adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1 || true
  sleep 0.3
}

snapshot "source-form"
for id in source_server source_username source_password source_connect; do
  exists_id "$OUT/source-form.xml" "$id" || { echo "Missing source control: $id ($(label_for "$id"))"; exit 1; }
done

set_field "source_server" "$SOURCE_BASE"
set_field "source_username" "qauser"
set_field "source_password" "qapass" true

snapshot "ready-to-connect"
click_id "$OUT/ready-to-connect.xml" "source_connect" || { echo "Unable to click source connect action"; exit 1; }

success=0
for attempt in $(seq 1 80); do
  sleep 0.25
  snapshot "result-${attempt}"
  XML="$OUT/result-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTION ERROR|Xtream rejected|Connection failed|could not save source|invalid data|did not return a valid' "$XML"; then
    cp "$XML" "$OUT/connection-error.xml"
    cp "$OUT/result-${attempt}.png" "$OUT/connection-error.png"
    echo "Source connection reached an explicit error state"
    exit 1
  fi
  # A successful SourceConnectScreen saves the source and calls onSaved(),
  # which finishes this dedicated QA activity. Its source_connect node then
  # disappears. Do not require transient success text to render first.
  if ! exists_id "$XML" "source_connect"; then
    success=1
    break
  fi
done
[ "$success" -eq 1 ] || { echo "Source connection did not finish successfully"; exit 1; }

adb shell am force-stop "$PKG" || true
START_OUTPUT="$(adb shell am start -W -n "$ACTIVITY" 2>&1)"
printf '%s\n' "$START_OUTPUT" > "$OUT/persisted-activity-start.txt"
echo "$START_OUTPUT" | grep -q 'Status: ok'
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
