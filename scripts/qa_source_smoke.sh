#!/usr/bin/env bash
set -euo pipefail
# Runner-side source fixture validation. The emulator path is checked separately.
./scripts/start_qa_source.sh
./scripts/qa_source_server_test.sh
