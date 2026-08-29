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
# Use a dedicated in-process fixture port. The workflow also starts a legacy
# background fixture on 8765; keeping this regression fixture on its own port
# prevents bind races when the emulator runner changes process lifecycles.
port = int(os.environ.get("QA_SOURCE_PORT", "8766"))
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

    if not os.path.isfile(apk) or os.path.getsize(apk) == 0:
        print(f"[QA][FAIL] APK missing or empty: {apk}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    print(f"[QA] Clearing prior app state: com.xsportsx.app.{mode}", flush=True)
    subprocess.run(["adb", "shell", "pm", "clear", f"com.xsportsx.app.{mode}"], text=True, capture_output=True, check=False)

    print(f"[QA] Installing APK: {apk}", flush=True)
    install = subprocess.run(
        ["adb", "install", "-r", "-d", "--no-incremental", apk],
        text=True,
        capture_output=True,
        check=False,
    )
    if install.stdout:
        print(install.stdout.strip(), flush=True)
    if install.stderr:
        print(install.stderr.strip(), flush=True)
    if install.returncode != 0:
        print(f"[QA][FAIL] APK installation failed with exit code {install.returncode}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    expected_package = f"com.xsportsx.app.{mode}"
    pm_path = subprocess.run(
        ["adb", "shell", "pm", "path", expected_package],
        text=True,
        capture_output=True,
        check=False,
    )
    if pm_path.returncode != 0 or "package:" not in pm_path.stdout:
        print(f"[QA][FAIL] Installed package not found: {expected_package}", file=sys.stderr, flush=True)
        print(pm_path.stdout.strip(), file=sys.stderr, flush=True)
        print(pm_path.stderr.strip(), file=sys.stderr, flush=True)
        raise SystemExit(1)
    print(f"[QA] Installed package verified: {expected_package}", flush=True)

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
