#!/usr/bin/env python3
"""Keep source expansion lightweight: track candidate catalogs for background diffing.

No playlist is downloaded or exposed to playback here. A backend job can compare
channel identities against the existing curated public pool and only promote new,
verified sports channels after health/rights checks.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT=Path('data/source_catalog_diff.json')
CATALOGS=[
 {'name':'iptv-org sports','kind':'playlist','url':'https://iptv-org.github.io/iptv/categories/sports.m3u','priority':100},
 {'name':'Free-TV IPTV','kind':'playlist','url':'https://github.com/Free-TV/IPTV','priority':95},
 {'name':'FreeCastHub Sports','kind':'playlist','url':'https://github.com/freecasthub/public-iptv','priority':90},
 {'name':'World IPTV','kind':'aggregator','url':'https://github.com/Romaxa55/world_ip_tv','priority':70},
 {'name':'Shovo','kind':'derived-aggregator','url':'https://github.com/shovo127/IPTV-By-Shovo','priority':40}
]
POLICY={
 'existing_sources_are_deduped':True,
 'promote_only_unique':True,
 'require_https':True,
 'require_health_check':True,
 'require_public_or_authorized':True,
 'exclude_catalog_sports':['tennis','golf','track & field','swimming & diving','cross country','field hockey','water polo','beach volleyball','mens volleyball','rowing'],
 'never_import_credentials':True,
 'never_import_telegram_stream_urls':True,
 'never_block_playback':True
}

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({'schema':1,'generatedAt':datetime.now(timezone.utc).isoformat(),'catalogs':CATALOGS,'policy':POLICY},indent=2)+'\n',encoding='utf-8')
 print('wrote supplemental source diff manifest')
if __name__=='__main__':main()
