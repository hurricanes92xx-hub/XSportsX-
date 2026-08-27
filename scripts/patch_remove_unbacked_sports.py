#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("app/src/main/java/com/xsportsx/app")
TARGETS = ('SportVisual("ESPORTS"', 'SportVisual("ACTION SPORTS"')
REMOVED = 0

for path in ROOT.rglob("*.kt"):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    kept = []
    changed = False
    for line in lines:
        if any(token in line for token in TARGETS):
            REMOVED += 1
            changed = True
            continue
        kept.append(line)
    if changed:
        path.write_text("".join(kept), encoding="utf-8")

# Do not allow these unbacked categories to reappear through generated/UI text.
for path in ROOT.rglob("*.kt"):
    text = path.read_text(encoding="utf-8")
    if '"ESPORTS"' in text or '"ACTION SPORTS"' in text:
        raise SystemExit(f"unbacked sport category remains in {path}")

print(f"Removed {REMOVED} unbacked Esports/Action Sports catalog entries")
