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
    # Android images can transiently expose an empty hierarchy immediately after launch.
    # Keep the diagnostic instead of silently treating a missing XML as a valid screen.
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
    if any(term in value.strip().casefold() for term in terms for value in values):
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

# Type ASCII through ADB, but do not trust one-shot URL injection. Android's
# input command has shell/special-character edge cases; URLs are therefore
# assembled from safe text chunks plus explicit punctuation key events.
type_value(){
  local value="$1"
  python3 - "$value" <<'PY'
import subprocess,sys
s=sys.argv[1]
chunk=[]

def flush():
    if chunk:
        text=''.join(chunk).replace(' ','%s')
        subprocess.run(['adb','shell','input','text',text],check=True)
        chunk.clear()

for ch in s:
    if ch.isalnum() or ch in '_-@':
        chunk.append(ch)
        continue
    flush()
    if ch == '/':
        subprocess.run(['adb','shell','input','keyevent','KEYCODE_SLASH'],check=True)
    elif ch == '.':
        subprocess.run(['adb','shell','input','keyevent','KEYCODE_PERIOD'],check=True)
    elif ch == ':':
        # KEYCODE_COLON is available on modern Android; fall back to input text
        # for images whose keymap does not expose it.
        p=subprocess.run(['adb','shell','input','keyevent','KEYCODE_COLON'])
        if p.returncode != 0:
            subprocess.run(['adb','shell','input','text',':'],check=True)
    elif ch == ' ':
        subprocess.run(['adb','shell','input','keyevent','KEYCODE_SPACE'],check=True)
    else:
        subprocess.run(['adb','shell','input','text',ch],check=True)
flush()
PY
}

field_value(){
  local file="$1" label="$2"
  python3 - "$file" "$label" <<'PY'
import sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); label=sys.argv[2].casefold()
for n in root.iter('node'):
    if n.attrib.get('class') == 'android.widget.EditText':
        # Compose exposes the semantic label on a child View; inspect the subtree.
        if any(x.attrib.get('content-desc','').strip().casefold()==label for x in n.iter('node')):
            print(n.attrib.get('text',''))
            raise SystemExit
raise SystemExit(1)
PY
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
  # Mobile uses CONNECT NOW. TV uses the top-right SETTINGS button to open
  # the source chooser, then SIGN IN ON TV to reach the same SourceConnectScreen.
  click_text "CONNECT NOW" || click_text "CONNECT NOW →" || click_text "SETTINGS" || click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 1
  if [ "$attempt" -ge 2 ]; then
    click_text "SIGN IN ON TV" || true
  fi
done

[ -n "$SOURCE_XML" ] || { echo "Missing source form"; snapshot "source-form-missing"; exit 1; }

python3 - "$SOURCE_XML" <<'PY'
import os,subprocess,sys,xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
def bound(term):
    term=term.casefold()
    for n in root.iter('node'):
        if n.attrib.get('content-desc','').strip().casefold()==term or n.attrib.get('text','').strip().casefold()==term:
            b=n.attrib.get('bounds','')
            try:
                a,c=b.split(']['); x1,y1=map(int,a.strip('[]').split(',')); x2,y2=map(int,c.strip('[]').split(',')); return (x1+x2)//2,(y1+y2)//2
            except Exception: pass
    return None
fields=[bound('Server URL'),bound('Username'),bound('Password')]
if any(v is None for v in fields): raise SystemExit('Expected stable source field semantics')
values=[os.environ.get('QA_SOURCE_BASE','http://127.0.0.1:8765'),'qauser','qapass']
for (x,y),value in zip(fields,values):
    subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
    subprocess.run(['adb','shell','input','keyevent','KEYCODE_MOVE_END'],check=True)
    type_value=value
    # Keep the helper logic in this process so punctuation is deterministic.
    import re
    chunk=[]
    def flush():
        if chunk:
            subprocess.run(['adb','shell','input','text',''.join(chunk).replace(' ','%s')],check=True); chunk.clear()
    for ch in value:
        if ch.isalnum() or ch in '_-@': chunk.append(ch)
        else:
            flush()
            key={'/':'KEYCODE_SLASH','.':'KEYCODE_PERIOD',':':'KEYCODE_COLON',' ':'KEYCODE_SPACE'}.get(ch)
            if key: subprocess.run(['adb','shell','input','keyevent',key],check=True)
            else: subprocess.run(['adb','shell','input','text',ch],check=True)
    flush()
PY

sleep 1
snapshot "03-filled"
if [ "$(field_value "$OUT/03-filled.xml" "Server URL" 2>/dev/null || true)" != "$SOURCE_BASE" ]; then
  echo "Server URL was not injected correctly"
  echo "Observed server field: $(field_value "$OUT/03-filled.xml" "Server URL" 2>/dev/null || true)"
  exit 1
fi
if [ "$(field_value "$OUT/03-filled.xml" "Username" 2>/dev/null || true)" != "qauser" ]; then
  echo "Username was not injected correctly"
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
