from pathlib import Path
import re

p=Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file(): raise SystemExit(f"Missing TV source: {p}")
s=p.read_text(encoding="utf-8")
if 'TvSport("NCAA VB"' in s:
    print("NCAA volleyball TV badge already present")
else:
    logo="https://commons.wikimedia.org/wiki/Special:Redirect/file/NCAA_Volleyball_wordmark_color.svg"
    m=re.search(r'(\s*TvSport\("NCAA BB"[^\n]*\),)',s)
    if not m: raise SystemExit("NCAA BB TV badge entry not found after sports patches")
    s=s[:m.end()]+f'\n    TvSport("NCAA VB","NCAA","{logo}"),' + s[m.end():]
p.write_text(s,encoding="utf-8")
print("NCAA Volleyball TV badge applied")