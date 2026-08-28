#!/usr/bin/env bash
set -euo pipefail

# QA fixture is owned by the GitHub Actions background service in the workflow.
APK="$1"
MODE="$2"
OUTDIR="$3"

if [[ -z "$APK" || -z "$MODE" || -z "$OUTDIR" ]]; then
  echo "Usage: $0 APK mobile|tv OUTPUT_DIR" >&2
  exit 2
fi

SOURCE_BASE="${QA_SOURCE_BASE:-http://10.0.2.2:8765}"
HOST_SOURCE_BASE="${QA_SOURCE_HOST_BASE:-http://127.0.0.1:8765}"

echo "Starting XSportsX ${MODE} emulator regression"
adb start-server
adb wait-for-device
adb_state="$(adb -s emulator-5554 get-state)"
boot_completed="$(adb -s emulator-5554 shell getprop sys.boot_completed | tr -d '\r')"
echo "ADB state: ${adb_state}"
echo "Boot completed: ${boot_completed}"
test "$adb_state" = device
test "$boot_completed" = 1

echo "Checking QA source fixture on host at ${HOST_SOURCE_BASE}/health"
server_ready=0
for i in $(seq 1 30); do
  if curl -fsS --max-time 2 "${HOST_SOURCE_BASE}/health" >/dev/null; then
    server_ready=1
    break
  fi
  sleep 1
done

if [[ "$server_ready" != 1 ]]; then
  echo "QA source fixture is not reachable at ${HOST_SOURCE_BASE}/health"
  echo "Host-side diagnostic:"
  curl -v --max-time 3 "${HOST_SOURCE_BASE}/health" || true
  exit 1
fi

echo "QA source fixture is alive on the host. Android will use ${SOURCE_BASE}."
chmod +x scripts/qa_regression_test.sh
QA_MODE="$MODE" QA_SOURCE_BASE="$SOURCE_BASE" QA_SOURCE_HOST_BASE="$HOST_SOURCE_BASE" ./scripts/qa_regression_test.sh "$APK" "$OUTDIR"
