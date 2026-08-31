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
  adb shell uiautomator dump --compressed /sdcard/window.xml >/dev/null 2>&1 || true
  adb shell cat /sdcard/window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  if [ ! -s "$OUT/${name}.xml" ]; then
    adb shell uiautomator dump --compressed /sdcard/source.xml >/dev/null 2>&1 || true
    adb shell cat /sdcard/source.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
}
find_bounds(){
  local file="$1"; shift
  python3 - "$file" "$@" <<'PY'
import re,sys
xml=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
terms=sys.argv[2:]
for term in terms:
    pat=re.compile(r'<node[^>]*?(?:text="'+re.escape(term)+r'"|content-desc="'+re.escape(term)+r'")[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',re.I)
    m=pat.search(xml)
    if m:
        x1,y1,x2,y2=map(int,m.groups()); print((x1+x2)//2,(y1+y2)//2); raise SystemExit(0)
raise SystemExit(1)
PY
}
click_text(){
  local text="$1" bounds
  snapshot "click-probe"
  bounds="$(find_bounds "$OUT/click-probe.xml" "$text" 2>/dev/null || true)"
  if [ -n "$bounds" ]; then read -r x y <<< "$bounds"; adb shell input tap "$x" "$y"; return 0; fi
  return 1
}
# Navigate to Source Center. Stable Compose semantics are preferred; text is retained as fallback.
for attempt in $(seq 1 10); do
  snapshot "source-nav-${attempt}"
  XML="$OUT/source-nav-${attempt}.xml"
  if grep -Eqi 'Server URL|XTREAM CODES|Username|Password|TEST &amp; CONNECT|TEST & CONNECT' "$XML"; then
    cp "$XML" "$OUT/01-source.xml"; cp "$OUT/source-nav-${attempt}.png" "$OUT/01-source.png"; break
  fi
  click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 2
done
SOURCE_XML="$OUT/01-source.xml"
[ -s "$SOURCE_XML" ] || { echo "Missing source UI hierarchy"; exit 1; }
grep -Eqi 'Server URL|XTREAM CODES|Username|Password' "$SOURCE_XML" || { echo "Missing source form"; exit 1; }
# Prefer stable Compose semantic bounds for the three Xtream fields.
python3 - "$SOURCE_XML" <<'PY'
import re, subprocess, os, sys
xml=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
def bound(term):
    for attr in ('content-desc','text'):
        m=re.search(r'<node[^>]*?'+re.escape(attr)+r'="'+re.escape(term)+r'"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml,re.I)
        if m:
            x1,y1,x2,y2=map(int,m.groups()); return (x1+x2)//2,(y1+y2)//2
    return None
fields=[bound('Server URL'),bound('Username'),bound('Password')]
if any(v is None for v in fields):
    # Fallback to editable/focusable nodes in visual top-to-bottom order.
    raw=[]
    for m in re.finditer(r'<node[^>]*?(?:class="android\.widget\.EditText"|focusable="true")[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
        x1,y1,x2,y2=map(int,m.groups()); raw.append(((y1,x1),(x1+x2)//2,(y1+y2)//2))
    fields=[(x,y) for _,x,y in sorted(raw)[:3]] if len(raw)>=3 else fields
if any(v is None for v in fields): raise SystemExit('Expected stable source field semantics')
values=[os.environ.get('QA_SOURCE_BASE','http://127.0.0.1:8765'),'qauser','qapass']
for (x,y),value in zip(fields,values):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_MOVE_END'],check=True)
    subprocess.run(['adb','shell','input','text',value.replace(' ','%s')],check=True)
PY
# The production button now has a stable content description.
clicked=0
for attempt in $(seq 1 5); do
  if click_text "TEST & CONNECT" || click_text "CONNECT SOURCE" || click_text "TESTING SOURCE"; then clicked=1; break; fi
  sleep 1
done
[ "$clicked" -eq 1 ] || { echo "Missing source connect action"; exit 1; }
# Connection is asynchronous; allow the UI and local fixture enough time to settle.
for attempt in $(seq 1 10); do
  sleep 1
  snapshot "03-connected-${attempt}"
  XML="$OUT/03-connected-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTED|Connected • Xtream|Connected.*Xtream|SOURCE SAVED|Connection successful' "$XML"; then
    cp "$XML" "$OUT/03-connected.xml"; cp "$OUT/03-connected-${attempt}.png" "$OUT/03-connected.png"
    echo "Xtream source login/pull smoke test passed"
    exit 0
  fi
  # A successful save can navigate away; the source store success is still a valid completion state.
  if grep -Eqi 'SOURCE CENTER|CONNECT SOURCE' "$XML" && ! grep -Eqi 'SOURCE CONNECTION ERROR|rejected the username|Connection failed' "$XML"; then
    # Keep polling rather than treating a transient navigation frame as success.
    true
  fi
done
echo "Source connection did not reach a success state"
exit 1
