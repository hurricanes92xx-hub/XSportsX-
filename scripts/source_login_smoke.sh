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
sleep 5
click_text() {
  local text="$1" xml bounds
  adb shell uiautomator dump /sdcard/source.xml >/dev/null 2>&1 || true
  xml="$(adb shell cat /sdcard/source.xml 2>/dev/null || true)"
  bounds="$(printf '%s' "$xml" | sed 's/></>\n</g' | grep -m1 "text=\"${text}\"" | sed -n 's/.*bounds="\[\([0-9]*\),\([0-9]*\)\]\[\([0-9]*\),\([0-9]*\)\]".*/\1 \2 \3 \4/p')"
  [ -n "$bounds" ] || return 1
  read -r x1 y1 x2 y2 <<< "$bounds"
  adb shell input tap $(( (x1+x2)/2 )) $(( (y1+y2)/2 ))
}
click_text "Xtream" || click_text "Xtream Codes" || true
sleep 1
adb shell uiautomator dump /sdcard/source-fields.xml >/dev/null 2>&1 || true
adb shell cat /sdcard/source-fields.xml > "$OUT/xtream-fields.xml" || true
QA_SOURCE_BASE="$SOURCE_BASE" python3 - <<'PY'
import re, subprocess, os
xml=subprocess.check_output(['adb','shell','cat','/sdcard/source-fields.xml'],text=True,errors='ignore')
fields=[]
for m in re.finditer(r'<node[^>]*class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
    x1,y1,x2,y2=map(int,m.groups()); fields.append(((y1,x1),(x1+x2)//2,(y1+y2)//2))
fields.sort()
values=[os.environ.get('QA_SOURCE_BASE','http://127.0.0.1:8765'),'qauser','qapass']
if len(fields) < 3: raise SystemExit(f'Expected 3 source fields, found {len(fields)}')
for i,(_,x,y) in enumerate(fields[:3]):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_CTRL_A'],check=False)
    subprocess.run(['adb','shell','input','text',values[i]],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_BACK'],check=False)
PY
click_text "TEST & CONNECT" || click_text "CONNECT SOURCE" || click_text "LOGIN" || click_text "Login" || click_text "CONNECT" || click_text "Connect" || click_text "SIGN IN" || click_text "Sign In"
sleep 5
adb exec-out screencap -p > "$OUT/after-xtream.png"
adb shell uiautomator dump /sdcard/after.xml >/dev/null 2>&1 || true
adb shell cat /sdcard/after.xml > "$OUT/after.xml" || true
grep -Eq 'QA Sports One|QA Sports Two|SPORTS COMMAND CENTER|Connected|SOURCE READY|SOURCE SAVED|Connection successful' "$OUT/after.xml"
echo "Xtream source login/pull smoke test passed"
