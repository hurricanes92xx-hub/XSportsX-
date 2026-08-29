#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
MODE="${2:?mobile|tv mode required}"
OUTDIR="${3:?output directory required}"
PORT="${QA_SOURCE_PORT:-8765}"

python3 - "$APK" "$MODE" "$OUTDIR" "$PORT" <<'PY'
import os
import subprocess
import sys
import threading
import time
import urllib.request
from scripts.qa_source_server import Handler, ReusableThreadingHTTPServer

apk, mode, outdir, port = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
base = f"http://127.0.0.1:{port}"
server = ReusableThreadingHTTPServer(("0.0.0.0", port), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=2) as r:
                if r.status == 200: break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise SystemExit("[QA][FAIL] fixture health timeout")

    reverse = subprocess.run(["adb", "reverse", f"tcp:{port}", f"tcp:{port}"], text=True, capture_output=True)
    print(f"[QA] adb reverse tcp:{port} -> tcp:{port}: rc={reverse.returncode}", flush=True)
    if reverse.returncode != 0: raise SystemExit("[QA][FAIL] adb reverse failed")

    env = os.environ.copy()
    env.update(QA_MODE=mode, QA_SOURCE_BASE=base, QA_SOURCE_HOST_BASE=base, QA_SOURCE_PORT=str(port))
    result = subprocess.run(["bash", "scripts/qa_regression_test_v2.sh", apk, outdir], env=env, check=False)
    raise SystemExit(result.returncode)
finally:
    server.shutdown()
    server.server_close()
PY
