#!/usr/bin/env python3
from pathlib import Path

# Release builds use checked-in assets. Do not mutate the working tree or
# depend on external logo hosts during CI.
ROOT = Path('app/src/main/assets/brand_logos')
REQUIRED = ('wwe.svg', 'aew.svg', 'tna.svg', 'fs1.svg', 'acc.svg', 'sec.svg')
missing = [name for name in REQUIRED if not (ROOT / name).is_file() or (ROOT / name).stat().st_size == 0]
if missing:
    raise SystemExit('missing bundled logo assets: ' + ', '.join(missing))
print('bundled brand logo pack verified; no downloads performed')
