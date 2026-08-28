#!/usr/bin/env bash
set -euo pipefail

APK="${1:?APK path required}"
MODE="${2:?mobile|tv mode required}"
OUTDIR="${3:?output directory required}"

# The emulator action can interfere with background child-process lifecycle.
# Keep the fixture server in the foreground Python process and run the actual
# regression as its child so the fixture cannot disappear between health checks.
python3 - "$APK" "$MODE" "$OUTDIR" <<'PY'
import os
import subprocess
import sys
import threading
import time
import urllib.request

from scripts.qa_source_server import Handler, ReusableThreadingHTTPServer

apk, mode, outdir = sys.argv[1:4]
port = int(os.environ.get("QA_SOURCE_PORT", "8765"))
source_base = f"http://10.0.2.2:{port}"
host_base = f"http://127.0.0.1:{port}"

server = ReusableThreadingHTTPServer(("0.0.0.0", port), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    print(f"[QA] fixture started in-process on 0.0.0.0:{port}", flush=True)
    last_error = None
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{host_base}/health", timeout=2) as response:
                if response.status == 200:
                    print("[QA] host fixture health check passed", flush=True)
                    break
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    else:
        print(f"[QA][FAIL] fixture never became reachable: {last_error}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    env = os.environ.copy()
    env["QA_MODE"] = mode
    env["QA_SOURCE_BASE"] = source_base
    env["QA_SOURCE_HOST_BASE"] = host_base
    env["QA_SOURCE_PORT"] = str(port)

    # Secondary deterministic route: Android localhost -> host through ADB.
    reverse = subprocess.run(
        ["adb", "reverse", f"tcp:{port}", f"tcp:{port}"],
        text=True,
        capture_output=True,
        check=False,
    )
    print(f"[QA] adb reverse tcp:{port} -> tcp:{port}: rc={reverse.returncode}", flush=True)
    if reverse.stdout:
        print(reverse.stdout.strip(), flush=True)
    if reverse.stderr:
        print(reverse.stderr.strip(), flush=True)

    print(f"[QA] Android source URL: {source_base}", flush=True)

    # qa_regression_test.sh resolves the installed launcher's authoritative
    # ComponentName from the package manager. Do not rewrite ACTIVITY here:
    # the flavor applicationId (com.xsportsx.app.mobile/tv) intentionally
    # differs from the Kotlin namespace (com.xsportsx.app), and Android needs
    # the complete package/class component returned by cmd package.
    qa_script = "scripts/qa_regression_test.sh"
    print("[QA] launcher target will be resolved from installed APK", flush=True)

    result = subprocess.run(
        ["bash", qa_script, apk, outdir],
        env=env,
        check=False,
    )
    raise SystemExit(result.returncode)
finally:
    server.shutdown()
    server.server_close()
PY
