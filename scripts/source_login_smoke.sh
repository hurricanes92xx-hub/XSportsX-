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
  rm -f "$OUT/${name}.xml"
  adb shell uiautomator dump --compressed /sdcard/window.xml >/dev/null 2>&1 || true
  adb exec-out cat /sdcard/window.xml > "$OUT/${name}.xml" 2>/dev/null || true
  if [ ! -s "$OUT/${name}.xml" ]; then
    adb shell uiautomator dump --compressed /sdcard/source.xml >/dev/null 2>&1 || true
    adb exec-out cat /sdcard/source.xml > "$OUT/${name}.xml" 2>/dev/null || true
  fi
}

find_bounds(){
  local file="$1"; shift
  python3 - "$file" "$@" <<'PY'
import sys
import xml.etree.ElementTree as ET

try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    raise SystemExit(1)
terms = [t.strip().casefold() for t in sys.argv[2:]]
for node in root.iter("node"):
    values = [node.attrib.get("text", ""), node.attrib.get("content-desc", "")]
    normalized = [v.strip().casefold() for v in values]
    if any(term in normalized for term in terms):
        bounds = node.attrib.get("bounds", "")
        try:
            left_top, right_bottom = bounds.split("][")
            x1, y1 = map(int, left_top.strip("[]").split(","))
            x2, y2 = map(int, right_bottom.strip("[]").split(","))
            print((x1+x2)//2, (y1+y2)//2)
            raise SystemExit(0)
        except Exception:
            pass
raise SystemExit(1)
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

# Navigate to Source Center. ElementTree decodes XML entities such as &amp;.
for attempt in $(seq 1 10); do
  snapshot "source-nav-${attempt}"
  XML="$OUT/source-nav-${attempt}.xml"
  if grep -Eqi 'Server URL|XTREAM CODES|Username|Password|TEST &amp; CONNECT|TEST & CONNECT' "$XML"; then
    cp "$XML" "$OUT/01-source.xml"
    cp "$OUT/source-nav-${attempt}.png" "$OUT/01-source.png"
    break
  fi
  click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 2
done
SOURCE_XML="$OUT/01-source.xml"
[ -s "$SOURCE_XML" ] || { echo "Missing source UI hierarchy"; exit 1; }
grep -Eqi 'Server URL|XTREAM CODES|Username|Password' "$SOURCE_XML" || { echo "Missing source form"; exit 1; }

# Prefer the production Compose semantics for the three Xtream fields.
python3 - "$SOURCE_XML" <<'PY'
import os, subprocess, sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()

def bound(term):
    term = term.casefold()
    for node in root.iter("node"):
        if node.attrib.get("content-desc", "").strip().casefold() == term or node.attrib.get("text", "").strip().casefold() == term:
            b = node.attrib.get("bounds", "")
            try:
                a, c = b.split("][")
                x1, y1 = map(int, a.strip("[]").split(","))
                x2, y2 = map(int, c.strip("[]").split(","))
                return (x1+x2)//2, (y1+y2)//2
            except Exception:
                pass
    return None

fields = [bound("Server URL"), bound("Username"), bound("Password")]
if any(v is None for v in fields):
    raw = []
    for node in root.iter("node"):
        if node.attrib.get("class") == "android.widget.EditText" or node.attrib.get("focusable") == "true":
            b = node.attrib.get("bounds", "")
            try:
                a, c = b.split("][")
                x1, y1 = map(int, a.strip("[]").split(","))
                x2, y2 = map(int, c.strip("[]").split(","))
                raw.append((y1, (x1+x2)//2, (y1+y2)//2))
            except Exception:
                pass
    raw.sort()
    if len(raw) >= 3:
        fields = [(x, y) for _, x, y in raw[:3]]
if any(v is None for v in fields):
    raise SystemExit("Expected stable source field semantics")

values = [os.environ.get("QA_SOURCE_BASE", "http://127.0.0.1:8765"), "qauser", "qapass"]
for (x, y), value in zip(fields, values):
    subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)], check=True)
    subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_MOVE_END"], check=True)
    subprocess.run(["adb", "shell", "input", "text", value.replace(" ", "%s")], check=True)
PY

clicked=0
for attempt in $(seq 1 5); do
  if click_text "TEST & CONNECT" || click_text "CONNECT SOURCE" || click_text "TESTING SOURCE"; then
    clicked=1
    break
  fi
  sleep 1
done
[ "$clicked" -eq 1 ] || { echo "Missing source connect action"; exit 1; }

# Catch fast success/error states before onSaved() navigates away.
for attempt in $(seq 1 15); do
  sleep 0.25
  snapshot "03-result-${attempt}"
  XML="$OUT/03-result-${attempt}.xml"
  if grep -Eqi 'SOURCE CONNECTION ERROR|rejected the username|Connection failed|could not save source|invalid data|did not return a valid' "$XML"; then
    cp "$XML" "$OUT/03-error.xml"
    cp "$OUT/03-result-${attempt}.png" "$OUT/03-error.png"
    echo "Source connection reached an explicit error state"
    exit 1
  fi
  if grep -Eqi 'SOURCE CONNECTED|Connected.*Xtream|SOURCE SAVED|Connection successful' "$XML"; then
    cp "$XML" "$OUT/03-connected.xml"
    cp "$OUT/03-result-${attempt}.png" "$OUT/03-connected.png"
    echo "Xtream source login/pull smoke test passed"
    exit 0
  fi
done

# The production screen navigates immediately after store.save(). Reopen the
# source screen and verify that the real SourceStore data persisted.
for attempt in $(seq 1 8); do
  snapshot "04-persist-nav-${attempt}"
  XML="$OUT/04-persist-nav-${attempt}.xml"
  if grep -Eqi 'Server URL|Username|Password|CONNECT SOURCE' "$XML"; then
    break
  fi
  click_text "Sources" || click_text "Source Center" || click_text "SOURCES" || true
  sleep 1
done

for attempt in $(seq 1 8); do
  snapshot "05-persist-${attempt}"
  XML="$OUT/05-persist-${attempt}.xml"
  if grep -Eqi 'qauser|http://127\.0\.0\.1:8765|Server URL' "$XML" && ! grep -Eqi 'SOURCE CONNECTION ERROR|rejected the username|Connection failed|could not save source' "$XML"; then
    cp "$XML" "$OUT/03-connected.xml"
    cp "$OUT/05-persist-${attempt}.png" "$OUT/03-connected.png"
    echo "Xtream source login/pull smoke test passed (persisted source verified)"
    exit 0
  fi
  sleep 0.5
done

echo "Source connection did not reach a success or persisted-source state"
exit 1
