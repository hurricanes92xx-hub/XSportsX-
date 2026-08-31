#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="${QA_PACKAGE:-com.xsportsx.app}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
mkdir -p "$OUT"

adb wait-for-device
adb get-state
adb shell getprop ro.build.version.sdk > "$OUT/device-sdk.txt"
adb shell wm size > "$OUT/device-size.txt"
adb reverse tcp:8765 tcp:8765 >/dev/null
adb reverse --list > "$OUT/adb-reverse.txt"
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
adb shell monkey -p "$PKG" 1 >/dev/null

snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  rm -f "$OUT/${name}.xml"
  rm -f /tmp/xsportsx-ui-dump.log
  if adb shell uiautomator dump --compressed /data/local/tmp/xsportsx-window.xml >/tmp/xsportsx-ui-dump.log 2>&1; then
    adb exec-out cat /data/local/tmp/xsportsx-window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
  if [ ! -s "$OUT/${name}.xml" ]; then
    cp /tmp/xsportsx-ui-dump.log "$OUT/${name}.ui-dump.log" 2>/dev/null || true
  fi
}

find_bounds(){
  local file="$1"; shift
  python3 - "$file" "$@" <<'PY'
import sys,xml.etree.ElementTree as ET
try: root=ET.parse(sys.argv[1]).getroot()
except Exception: raise SystemExit(1)
terms=[x.strip().casefold() for x in sys.argv[2:]]
for n in root.iter('node'):
    values=[n.attrib.get('text',''),n.attrib.get('content-desc','')]
    if any(term == value.strip().casefold() for term in terms for value in values):
        b=n.attrib.get('bounds','')
        try:
            a,c=b.split('][')
            x1,y1=map(int,a.strip('[]').split(',')); x2,y2=map(int,c.strip('[]').split(','))
            print((x1+x2)//2,(y1+y2)//2); raise SystemExit(0)
        except Exception: pass
raise SystemExit(1)
PY
}

has_source_form(){
  local file="$1"
  python3 - "$file" <<'PY'
import sys,xml.etree.ElementTree as ET
try: root=ET.parse(sys.argv[1]).getroot()
except Exception: raise SystemExit(1)
seen=set()
for n in root.iter('node'):
    for key in ('text','content-desc'):
        v=n.attrib.get(key,'').strip().casefold()
        if v in {'server url','username','password'}: seen.add(v)
raise SystemExit(0 if len(seen)==3 else 1)
PY
}

click_text(){
  local text="$1" bounds
  snapshot "click-probe"
  bounds="$(find_bounds "$OUT/click-probe.xml" "$text" 2>/dev/null || true)"
  if [ -n "$bounds" ]; then
    read -r x y <<< "$bounds"
    adb shell input tap "$x" "$y"
    return 0
  fi
  return 1
}

# Compose TextField values are not reliably exposed by uiautomator as a
# parent/child relationship. Resolve the label and the nearest editable node
# by geometry instead, then inject the complete value in one adb input command.
field_value(){
  local file="$1" label="$2"
  python3 - "$file" "$label" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); label=sys.argv[2].casefold()
def box(n):
    b=n.attrib.get('bounds','')
    try:
        a,c=b.split(']['); x1,y1=map(int,a.strip('[]').split(',')); x2,y2=map(int,c.strip('[]').split(',')); return x1,y1,x2,y2
    except Exception: return None
labels=[]
for n in root.iter('node'):
    if any(n.attrib.get(k,'').strip().casefold()==label for k in ('text','content-desc')):
        if box(n): labels.append(box(n))
if not labels: raise SystemExit(1)
for n in root.iter('node'):
    if n.attrib.get('class') not in ('android.widget.EditText','android.view.View'): continue
    b=box(n)
    if not b: continue
    cx=(b[0]+b[2])//2; cy=(b[1]+b[3])//2
    for lb in labels:
        lcx=(lb[0]+lb[2])//2; lcy=(lb[1]+lb[3])//2
        # TextField label/placeholder is normally inside or immediately left
        # of the editable region. Prefer the closest editable node vertically.
        if abs(cy-lcy) <= 180 and abs(cx-lcx) <= 700:
            print(n.attrib.get('text',''))
            raise SystemExit(0)
raise SystemExit(1)
PY
}

# Replace the contents of the focused Compose field without relying on
# KEYCODE_* characters for punctuation. `input text` handles the complete
# string atomically and avoids losing ':' '/' '.' during separate key events.
set_field(){
  local label="$1" value="$2" bounds x y
  snapshot "before-${label// /-}"
  bounds="$(find_bounds "$OUT/before-${label// /-}.xml" "$label" 2>/dev/null || true)"
  [ -n "$bounds" ] || { echo "Missing field: $label"; return 1; }
  read -r x y <<< "$bounds"
  adb shell input tap "$x" "$y"
  sleep 0.2
  # Select all where supported, then delete. This works for both an empty
  # initial TextField and a persisted value from a prior smoke-test attempt.
  adb shell input keyevent KEYCODE_MOVE_END || true
  for _ in $(seq 1 160); do adb shell input keyevent KEYCODE_DEL || true; done
  # Android's input text uses %s for spaces. The QA values contain no spaces;
  # quote the entire argument so punctuation reaches the input subsystem intact.
  adb shell input text "$value"
  sleep 0.4
  snapshot "after-${label// /-}"
}

SOURCE_XML=""
for attempt in $(seq 1 20); do
  snapshot "source-nav-${attempt}"
  XML="$OUT/source-nav-${attempt}.xml"
  if [ -s "$XML" ] && has_source_form "$XML"; then
    SOURCE_XML="$XML"
    cp "$XML" "$OUT/01-source.xml"
    cp "$OUT/source-nav-${attempt}.png" "$OUT/01-source.png"
    break
  fi
  click_text "CONNECT NOW" || click_text "CONNECT NOW →" || click_text "SETTINGS" || click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 1
  if [ "$attempt" -ge 2 ]; then click_text "SIGN IN ON TV" || true; fi
done

[ -n "$SOURCE_XML" ] || { echo "Missing source form"; snapshot "source-form-missing"; exit 1; }

set_field "Server URL" "$SOURCE_BASE"
set_field "Username" "qauser"
set_field "Password" "qapass"

sleep 0.5
snapshot "03-filled"
server="$(field_value "$OUT/03-filled.xml" "Server URL" 2>/dev/null || true)"
user="$(field_value "$OUT/03-filled.xml" "Username" 2>/dev/null || true)"
if [ "$server" != "$SOURCE_BASE" ]; then
  echo "Server URL was not injected correctly"
  echo "Observed server field: $server"
  exit 1
fi
if [ "$user" != "qauser" ]; then
  echo "Username was not injected correctly"
  echo "Observed username field: $user"
  exit 1
fi

adb shell input keyevent KEYCODE_BACK || true
sleep 1
clicked=0
for attempt in $(seq 1 10); do
  if click_text 'TEST & CONNECT' || click_text 'CONNECT SOURCE' || click_text 'TESTING SOURCE'; then clicked=1; break; fi
  adb shell input swipe 540 850 540 400 300 >/dev/null 2>&1 || true
  sleep 1
done
[ "$clicked" -eq 1 ] || { snapshot 'connect-missing'; echo 'Missing source connect action'; exit 1; }

for attempt in $(seq 1 30); do
  sleep 0.25
  snapshot "03-result-${attempt}"
  XML="$OUT/03-result-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTION ERROR|rejected the username|Connection failed|could not save source|invalid data|did not return a valid' "$XML"; then
    cp "$XML" "$OUT/03-error.xml"; cp "$OUT/03-result-${attempt}.png" "$OUT/03-error.png"
    echo 'Source connection reached an explicit error state'; exit 1
  fi
  if grep -Eqi 'SOURCE CONNECTED|Connected.*Xtream|SOURCE SAVED|Connection successful' "$XML"; then
    cp "$XML" "$OUT/03-connected.xml"; cp "$OUT/03-result-${attempt}.png" "$OUT/03-connected.png"
    echo 'Xtream source login/pull smoke test passed'; exit 0
  fi
done

echo 'Source connection did not reach a success state'; exit 1
