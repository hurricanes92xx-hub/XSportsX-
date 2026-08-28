#!/usr/bin/env bash
set -euo pipefail

APK="$1"
MODE="$2"
OUTDIR="$3"

if [[ -z "$APK" || -z "$MODE" || -z "$OUTDIR" ]]; then
  echo "Usage: $0 APK mobile|tv OUTPUT_DIR" >&2
  exit 2
fi

echo "Starting XSportsX ${MODE} emulator regression"
adb start-server
adb wait-for-device
adb_state="$(adb -s emulator-5554 get-state)"
boot_completed="$(adb -s emulator-5554 shell getprop sys.boot_completed | tr -d '\r')"
echo "ADB state: ${adb_state}"
echo "Boot completed: ${boot_completed}"
test "$adb_state" = device
test "$boot_completed" = 1

export QA_SOURCE_HOST=0.0.0.0
export QA_SOURCE_PORT=8765
rm -f qa-source.log
python3 scripts/qa_source_server.py >qa-source.log 2>&1 &
QA_SERVER_PID=$!

cleanup() {
  kill "$QA_SERVER_PID" 2>/dev/null || true
  wait "$QA_SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

server_ready=0
for i in $(seq 1 30); do
  if ! kill -0 "$QA_SERVER_PID" 2>/dev/null; then
    echo "QA source server exited unexpectedly."
    cat qa-source.log || true
    exit 1
  fi
  if curl -fsS http://127.0.0.1:8765/health >/dev/null; then
    server_ready=1
    break
  fi
  sleep 1
done

if [[ "$server_ready" != 1 ]]; then
  echo "QA source server did not become ready."
  cat qa-source.log || true
  exit 1
fi

curl -fsS http://10.0.2.2:8765/health >/dev/null

echo "QA source server reachable from emulator."
chmod +x scripts/qa_regression_test.sh
QA_MODE="$MODE" QA_SOURCE_BASE=http://10.0.2.2:8765 ./scripts/qa_regression_test.sh "$APK" "$OUTDIR"
