#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="${QA_PACKAGE:-com.xsportsx.app}"
SOURCE_BASE="${QA_SOURCE_BASE:-http://127.0.0.1:8765}"
mkdir -p "$OUT"
adb wait-for-device
adb reverse tcp:8765 tcp:8765 >/dev/null
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
adb shell monkey -p "$PKG" 1 >/dev/null
sleep 3
snapshot(){ local name="$1"; adb exec-out screencap -p > "$OUT/${name}.png"; adb shell uiautomator dump /sdcard/source.xml >/dev/null 2>&1 || true; adb shell cat /sdcard/source.xml > "$OUT/${name}.xml" || true; }
click_text(){
  local text="$1" xml bounds
  adb shell uiautomator dump /sdcard/source.xml >/dev/null 2>&1 || true
  xml="$(adb shell cat /sdcard/source.xml 2>/dev/null || true)"
  bounds="$(printf '%s' "$xml" | sed 's/></>\n</g' | grep -m1 "text=\"${text}\"" | sed -n 's/.*bounds="\[\([0-9]*\),\([0-9]*\)\]\[\([0-9]*\),\([0-9]*\)\]".*/\1 \2 \3 \4/p')"
  [ -n "$bounds" ] || return 1
  read -r x1 y1 x2 y2 <<< "$bounds"
  adb shell input tap $(( (x1+x2)/2 )) $(( (y1+y2)/2 ))
}
# Production app has a single SOURCE CENTER screen; do not expect an obsolete provider chooser.
click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
sleep 1
snapshot 01-source
if ! grep -Eq 'Server URL|XTREAM CODES|CONNECT SOURCE' "$OUT/01-source.xml"; then
  click_text "SOURCES" || click_text "Sources" || true
  sleep 1
  snapshot 02-source-retry
fi
SOURCE_XML="$OUT/01-source.xml"
[ -s "$SOURCE_XML" ] || SOURCE_XML="$OUT/02-source-retry.xml"
grep -Eq 'Server URL|XTREAM CODES|CONNECT SOURCE' "$SOURCE_XML" || { echo "Missing production source form"; exit 1; }
QA_SOURCE_BASE="$SOURCE_BASE" python3 - "$SOURCE_XML" <<'PY'
import re, subprocess, os, sys
xml=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
fields=[]
for m in re.finditer(r'<node[^>]*class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
    x1,y1,x2,y2=map(int,m.groups()); fields.append(((y1,x1),(x1+x2)//2,(y1+y2)//2))
fields.sort()
values=[os.environ.get('QA_SOURCE_BASE','http://127.0.0.1:8765'),'qauser','qapass']
if len(fields)<3: raise SystemExit(f'Expected 3 source fields, found {len(fields)}')
for i,(_,x,y) in enumerate(fields[:3]):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','text',values[i].replace(' ','%s')],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_BACK'],check=False)
PY
click_text "CONNECT SOURCE" || click_text "CONNECT" || click_text "TEST & CONNECT" || { echo "Missing source connect action"; exit 1; }
sleep 3
snapshot 03-connected
grep -Eq 'SOURCE SAVED|Connection successful|Connected|SOURCE READY' "$OUT/03-connected.xml" || { echo "Source connection did not reach a production success state"; exit 1; }
echo "Xtream source login/pull smoke test passed"
