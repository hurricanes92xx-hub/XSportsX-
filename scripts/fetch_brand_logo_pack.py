#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path('app/src/main/assets/brand_logos')
ROOT.mkdir(parents=True, exist_ok=True)

# Publicly accessible SVG copies of the brands, used only as local build assets.
# Existing checked-in logos remain the fallback if a download is unavailable.
LOGOS = {
    'wwe.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_Official_Logo.svg',
    'aew.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/All_Elite_Wrestling_logo_2023.svg',
    'tna.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/TNA_Wrestling_(2024)_Logo.svg',
    'fs1.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/Fox_Sports_1_logo.svg',
    'acc.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/ACC_Network_logo_fc_db.svg',
    'sec.svg': 'https://commons.wikimedia.org/wiki/Special:Redirect/file/SEC_Network_(2024).svg',
}

for name, url in LOGOS.items():
    target = ROOT / name
    tmp = target.with_suffix('.download')
    try:
        subprocess.run([
            'curl', '--fail', '--silent', '--show-error', '--location', '--retry', '3',
            '--connect-timeout', '10', '--max-time', '30', url, '-o', str(tmp)
        ], check=True)
        text = tmp.read_text(encoding='utf-8')
        if '<svg' not in text[:4096].lower():
            raise RuntimeError('download was not an SVG')
        target.write_text(text, encoding='utf-8')
        tmp.unlink(missing_ok=True)
        print(f'installed {name}')
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        if target.exists() and target.stat().st_size > 0:
            print(f'kept existing {name}: {exc}')
        else:
            raise SystemExit(f'logo pack download failed for {name}: {exc}')
