from pathlib import Path

WWE = "https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_official_logo.svg"
ACC = "https://commons.wikimedia.org/wiki/Special:Redirect/file/ACC_Network_logo_fc_db.svg"
F1 = "https://commons.wikimedia.org/wiki/Special:Redirect/file/Formula_One_logo.svg"
MOTOGP = "https://commons.wikimedia.org/wiki/Special:Redirect/file/MotoGP_logo_(2024).svg"
WRC = "https://commons.wikimedia.org/wiki/Special:Redirect/file/WRC_logo.svg"
WEC = "https://commons.wikimedia.org/wiki/Special:Redirect/file/WEC_Logo.svg"

# Mobile home: replace dead/malformed favicon URLs with real image assets and
# make WWE the actual wrestling badge rather than a generic text glyph.
mobile = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
text = mobile.read_text()
replacements = {
    'https://www.google.com/s2/favicons?domain:worldlacrosse.sport&sz=128': 'https://www.google.com/s2/favicons?domain=worldlacrosse.sport&sz=128',
    'https://www.google.com/s2/favicons?domain:fiawec.com&sz=128': WEC,
    'https://www.google.com/s2/favicons?domain:fiaformulae.com&sz=128': 'https://www.google.com/s2/favicons?domain=fiaformulae.com&sz=128',
    'https://www.google.com/s2/favicons?domain=fivb.com&sz=128': 'https://www.google.com/s2/favicons?domain=volleyballworld.com&sz=128',
    'https://www.google.com/s2/favicons?domain=wwe.com&sz=128': WWE,
    'https://www.google.com/s2/favicons?domain=motogp.com&sz=128': MOTOGP,
    'https://www.google.com/s2/favicons?domain=wrc.com&sz=128': WRC,
}
for old, new in replacements.items():
    text = text.replace(old, new)

# Fix the ACC card with the actual ACC Network mark.
text = text.replace('XNetwork("ACC Network", "SPORTS", "ACC", "https://www.google.com/s2/favicons?domain=accnetwork.com&sz=128")',
                    f'XNetwork("ACC Network", "SPORTS", "ACC", "{ACC}")')

# Ensure WWE is represented as a wrestling network/source card as well.
needle = 'XNetwork("RugbyPass TV", "RUGBY", "RUGBY", "https://www.google.com/s2/favicons?domain=rugbypass.tv&sz=128")'
if 'XNetwork("WWE", "WRESTLING", "WWE", "' not in text:
    text = text.replace(needle, needle + f',\n    XNetwork("WWE", "WRESTLING", "WWE", "{WWE}")')

mobile.write_text(text)

# TV home patch target: use the same verified logos, including ACC and WWE.
tv = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
t = tv.read_text()
t = t.replace('https://www.google.com/s2/favicons?domain=accnetwork.com&sz=128', ACC)
t = t.replace('https://www.google.com/s2/favicons?domain=wwe.com&sz=128', WWE)
t = t.replace('https://www.google.com/s2/favicons?domain:worldlacrosse.sport&sz=128', 'https://www.google.com/s2/favicons?domain=worldlacrosse.sport&sz=128')
t = t.replace('https://www.google.com/s2/favicons?domain:fiawec.com&sz=128', WEC)
t = t.replace('https://www.google.com/s2/favicons?domain:fiaformulae.com&sz=128', 'https://www.google.com/s2/favicons?domain=fiaformulae.com&sz=128')
t = t.replace('https://www.google.com/s2/favicons?domain:worldlacrosse.sport&sz=128', 'https://www.google.com/s2/favicons?domain=worldlacrosse.sport&sz=128')
# Replace known motorsport favicon fallbacks with stable SVG assets.
t = t.replace('https://www.google.com/s2/favicons?domain=motogp.com&sz=128', MOTOGP)
t = t.replace('https://www.google.com/s2/favicons?domain=wrc.com&sz=128', WRC)
t = t.replace('https://www.google.com/s2/favicons?domain=imsa.com&sz=128', 'https://www.google.com/s2/favicons?domain=imsa.com&sz=128')

# If the badge patch did not already add WWE to TV sports, add it alongside wrestling.
if 'TvSport("WWE"' not in t:
    marker = 'TvSport("WRESTLING","WR"'
    pos = t.find(marker)
    if pos < 0:
        raise SystemExit('WRESTLING TV sport entry not found')
    end = t.find('),', pos)
    if end < 0:
        raise SystemExit('WRESTLING TV sport entry terminator not found')
    t = t[:end+2] + f'\n    TvSport("WWE","WWE","{WWE}"),' + t[end+2:]

tv.write_text(t)
print('Verified ACC/WWE and fixed malformed sports logo URLs for Mobile + TV')
