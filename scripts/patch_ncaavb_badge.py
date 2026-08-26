from pathlib import Path

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file():
    raise SystemExit(f"Missing TV source: {p}")
s = p.read_text(encoding="utf-8")
if 'TvSport("NCAA VB"' in s:
    print("NCAA volleyball TV badge already present")
    raise SystemExit(0)
marker = '    TvSport("NCAA BB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),'
if marker not in s:
    raise SystemExit("NCAA BB TV badge marker not found after sports badge patch")
logo = "https://commons.wikimedia.org/wiki/Special:Redirect/file/NCAA_Volleyball_wordmark_color.svg"
s = s.replace(marker, marker + f'\n    TvSport("NCAA VB","NCAA","{logo}"),', 1)
p.write_text(s, encoding="utf-8")
print("Added NCAA Volleyball TV badge")
