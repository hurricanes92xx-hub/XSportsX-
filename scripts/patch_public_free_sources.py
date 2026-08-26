from pathlib import Path

files = {
    Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt"),
    Path("app/src/main/java/com/xsportsx/app/TvHome.kt"),
}

replacements = {
    "Connect your authorized source to unlock live event matching and network streams.":
        "Free public sports streams are available now. Add Xtream/M3U only for your own source.",
    "Connect Xtream/M3U, then XSportsX can match your live events and networks.":
        "Free public streams work without login. Add Xtream/M3U only for your own source.",
    "Connect your authorized source to turn these cards into playable source matches.":
        "Free public streams are playable without login. Add a private source for additional channels.",
    "Connect your authorized source to turn these cards into playable source matches.":
        "Free public streams are playable without login. Add a private source for additional channels.",
    "SPORTS NETWORKS","FREE SPORTS SOURCES",
    "LIVE SOURCES","NO LOGIN REQUIRED",
    "MobileSectionLabel(\"NETWORKS\", null)":
        "MobileSectionLabel(\"FREE SPORTS SOURCES\", \"NO LOGIN\")",
}

for path in files:
    if not path.is_file():
        continue
    s = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements.items():
        if isinstance(old, tuple):
            continue
        if old in s:
            s = s.replace(old, new)
            changed = True
    path.write_text(s, encoding="utf-8")
    print(f"Public free-source UI patch: {path} ({'changed' if changed else 'already clean'})")
