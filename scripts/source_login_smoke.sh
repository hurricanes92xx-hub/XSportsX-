#!/usr/bin/env bash
set -euo pipefail
APK="${1:?APK required}"
OUT="${2:-source-login-output}"
PKG="com.xsportsx.app"
mkdir -p "$OUT"
adb install -r -d "$APK"
adb shell am force-stop "$PKG" || true
adb shell monkey -p "$PKG" 1 >/dev/null
sleep 5

# Find a visible text node and click it using its UiAutomator bounds.
click_text() {
  local text="$1"
  local xml
  adb shell uiautomator dump /sdcard/source.xml >/dev/null 2>&1 || true
  xml="$(adb shell cat /sdcard/source.xml 2>/dev/null || true)"
  local bounds
  bounds="$(printf '%s' "$xml" | sed 's/></>\n</g' | grep -m1 "text=\"${text}\"" | sed -n 's/.*bounds="\[\([0-9]*\),\([0-9]*\)\]\[\([0-9]*\),\([0-9]*\)\]".*/\1 \2 \3 \4/p')"
  [ -n "$bounds" ] || return 1
  read -r x1 y1 x2 y2 <<< "$bounds"
  adb shell input tap $(( (x1+x2)/2 )) $(( (y1+y2)/2 ))
}

# Source chooser: support common labels used by the app. If the current build
# opens directly into source setup, the first click simply becomes unnecessary.
click_text "Xtream" || click_text "Xtream Codes" || true
sleep 1
adb shell uiautomator dump /sdcard/source-fields.xml >/dev/null 2>&1 || true
adb shell cat /sdcard/source-fields.xml > "$OUT/xtream-fields.xml" || true

# Fill EditText controls in screen order. This is intentionally limited to the
# isolated QA fixture values.
python3 - <<'PY'
import re, subprocess
xml=subprocess.check_output(['adb','shell','cat','/sdcard/source-fields.xml'],text=True,errors='ignore')
fields=[]
for m in re.finditer(r'<node[^>]*class="android\.widget\.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',xml):
    x1,y1,x2,y2=map(int,m.groups()); fields.append(((y1,x1),(x1+x2)//2,(y1+y2)//2))
fields.sort()
values=['http://10.0.2.2:8765','qauser','qapass']
for i,(_,x,y) in enumerate(fields[:3]):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_CTRL_A'],check=False)
    subprocess.run(['adb','shell','input','text',values[i]],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_TAB'],check=False)
PY

# Try the common submit labels; failure here means the UI contract needs repair.
click_text "LOGIN" || click_text "Login" || click_text "CONNECT" || click_text "Connect" || click_text "SIGN IN" || click_text "Sign In"
sleep 5
adb exec-out screencap -p > "$OUT/after-xtream.png"
adb shell uiautomator dump /sdcard/after.xml >/dev/null 2>&1 || true
adb shell cat /sdcard/after.xml > "$OUT/after.xml" || true
grep -Eq 'QA Sports One|QA Sports Two|SPORTS COMMAND CENTER' "$OUT/after.xml"
echo "Xtream source login/pull smoke test passed"
