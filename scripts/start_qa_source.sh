#!/usr/bin/env bash
set -euo pipefail
nohup python3 scripts/qa_source_server.py >/tmp/xsportsx-qa-source.log 2>&1 &
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8765/health >/dev/null; then exit 0; fi
  sleep 1
done
cat /tmp/xsportsx-qa-source.log
exit 1
