#!/usr/bin/env python3
"""Release-build compatibility hook for the committed TV schedule source.

TvHome.kt is already the canonical, compiling TV implementation. The previous
build-time source rewrite could create a different Kotlin source tree than the
one validated by Source QA, so this hook intentionally does not rewrite it.
"""

from pathlib import Path

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not path.exists():
    raise SystemExit(f"Missing expected TV source: {path}")

print("TV schedule source left unchanged; using committed canonical TvHome.kt")
