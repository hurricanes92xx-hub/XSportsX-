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
# Production has SOURCE CENTER directly in the main activity; navigate there if needed.
for attempt in $(seq 1 5); do
  snapshot "source-nav-${attempt}"
  if grep -Eq 'Server URL|XTREAM CODES|CONNECT SOURCE' "$OUT/source-nav-${attempt}.xml"; then
    cp "$OUT/source-nav-${attempt}.xml" "$OUT/01-source.xml"; cp "$OUT/source-nav-${attempt}.png" "$OUT/01-source.png"; break
  fi
  click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 2
  snapshot "source-nav-post-${attempt}"
  if grep -Eq 'Server URL|XTREAM CODES|CONNECT SOURCE' "$OUT/source-nav-post-${attempt}.xml"; then
    cp "$OUT/source-nav-post-${attempt}.xml" "$OUT/01-source.xml"; cp "$OUT/source-nav-post-${attempt}.png" "$OUT/01-source.png"; break
  fi
done
SOURCE_XML="$OUT/01-source.xml"
[ -s "$SOURCE_XML" ] || { echo "Missing production source form"; exit 1; }
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
