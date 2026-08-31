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
sleep 4
snapshot(){
  local name="$1"
  adb exec-out screencap -p > "$OUT/${name}.png"
  # Compose can intermittently reject an explicit dump path on cold emulator startup.
  # Use the standard window.xml path first, then fall back to source.xml.
  adb shell uiautomator dump --compressed /sdcard/window.xml >/dev/null 2>&1 || true
  adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  if [ ! -s "$OUT/${name}.xml" ]; then
    adb shell uiautomator dump --compressed /sdcard/source.xml >/dev/null 2>&1 || true
    adb shell cat /sdcard/source.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
}
click_text(){
  local text="$1" xml bounds
  snapshot "click-probe"
  xml="$(cat "$OUT/click-probe.xml" 2>/dev/null || true)"
  bounds="$(printf '%s' "$xml" | sed 's/></>\n</g' | grep -m1 -E "text=\"${text}\"|content-desc=\"${text}\"" | sed -n 's/.*bounds="\[\([0-9]*\),\([0-9]*\)\]\[\([0-9]*\),\([0-9]*\)\]".*/\1 \2 \3 \4/p')"
  [ -n "$bounds" ] || return 1
  read -r x1 y1 x2 y2 <<< "$bounds"
  adb shell input tap $(( (x1+x2)/2 )) $(( (y1+y2)/2 ))
}
# Source Center is a main-activity destination. Prefer semantic navigation, with retries for Compose startup.
for attempt in $(seq 1 8); do
  snapshot "source-nav-${attempt}"
  XML="$OUT/source-nav-${attempt}.xml"
  if grep -Eqi 'Server URL|XTREAM CODES|CONNECT SOURCE|Username|Password' "$XML"; then
    cp "$XML" "$OUT/01-source.xml"; cp "$OUT/source-nav-${attempt}.png" "$OUT/01-source.png"; break
  fi
  click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 2
  snapshot "source-nav-post-${attempt}"
  XML="$OUT/source-nav-post-${attempt}.xml"
  if grep -Eqi 'Server URL|XTREAM CODES|CONNECT SOURCE|Username|Password' "$XML"; then
    cp "$XML" "$OUT/01-source.xml"; cp "$OUT/source-nav-post-${attempt}.png" "$OUT/01-source.png"; break
  fi
done
SOURCE_XML="$OUT/01-source.xml"
[ -s "$SOURCE_XML" ] || { echo "Missing source UI hierarchy"; exit 1; }
grep -Eqi 'Server URL|XTREAM CODES|CONNECT SOURCE|Username|Password' "$SOURCE_XML" || { echo "Missing source form"; exit 1; }
QA_SOURCE_BASE="$SOURCE_BASE" python3 - "$SOURCE_XML" <<'PY'
import re, subprocess, os, sys
xml=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
# Compose text fields may be exposed as android.widget.EditText or as generic nodes.
fields=[]
for m in re.finditer(r'<node[^>]*?(?:class="android\.widget\.EditText"|text="(?:Server URL|Username|Password)"|content-desc="(?:Server URL|Username|Password)")[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
    x1,y1,x2,y2=map(int,m.groups()); fields.append((y1,(x1+x2)//2,(y1+y2)//2))
# De-duplicate overlapping semantic nodes and keep top-to-bottom order.
seen=set(); ordered=[]
for y,x,yy in sorted(fields):
    key=(round(x/5),round(yy/5))
    if key not in seen: seen.add(key); ordered.append((x,yy))
if len(ordered)<3:
    # Last-resort: collect editable/focusable nodes by class/content flags.
    for m in re.finditer(r'<node[^>]*?(?:focusable="true"|class="android\.widget\.EditText")[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
        x1,y1,x2,y2=map(int,m.groups()); key=(round(((x1+x2)//2)/5),round(((y1+y2)//2)/5))
        if key not in seen: seen.add(key); ordered.append(((x1+x2)//2,(y1+y2)//2))
        if len(ordered)>=3: break
if len(ordered)<3: raise SystemExit(f'Expected 3 source fields, found {len(ordered)}')
values=[os.environ.get('QA_SOURCE_BASE','http://127.0.0.1:8765'),'qauser','qapass']
for i,(x,y) in enumerate(ordered[:3]):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','text',values[i].replace(' ','%s')],check=True)
PY
click_text "CONNECT SOURCE" || click_text "CONNECT" || click_text "TEST & CONNECT" || { echo "Missing source connect action"; exit 1; }
sleep 3
snapshot 03-connected
grep -Eqi 'SOURCE SAVED|Connection successful|Connected|SOURCE READY' "$OUT/03-connected.xml" || { echo "Source connection did not reach a success state"; exit 1; }
echo "Xtream source login/pull smoke test passed"
