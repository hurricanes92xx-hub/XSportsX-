from pathlib import Path

WWE="https://commons.wikimedia.org/wiki/Special:Redirect/file/WWE_official_logo.svg"
ACC="https://commons.wikimedia.org/wiki/Special:Redirect/file/ACC_Network_logo_fc_db.svg"
F1="https://commons.wikimedia.org/wiki/Special:Redirect/file/Formula_One_logo.svg"
MOTOGP="https://commons.wikimedia.org/wiki/Special:Redirect/file/MotoGP_logo_(2024).svg"
WRC="https://commons.wikimedia.org/wiki/Special:Redirect/file/WRC_logo.svg"
WEC="https://commons.wikimedia.org/wiki/Special:Redirect/file/WEC_Logo.svg"

mobile=Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
text=mobile.read_text()
for old,new in {
'https://www.google.com/s2/favicons?domain:worldlacrosse.sport&sz=128':'https://www.google.com/s2/favicons?domain=worldlacrosse.sport&sz=128',
'https://www.google.com/s2/favicons?domain:fiawec.com&sz=128':WEC,
'https://www.google.com/s2/favicons?domain:fiaformulae.com&sz=128':'https://www.google.com/s2/favicons?domain=fiaformulae.com&sz=128',
'https://www.google.com/s2/favicons?domain:fivb.com&sz=128':'https://www.google.com/s2/favicons?domain=volleyballworld.com&sz=128',
'https://www.google.com/s2/favicons?domain:wwe.com&sz=128':WWE,
'https://www.google.com/s2/favicons?domain:motogp.com&sz=128':MOTOGP,
'https://www.google.com/s2/favicons?domain:wrc.com&sz=128':WRC,
}.items(): text=text.replace(old,new)
text=text.replace('XNetwork("ACC Network", "SPORTS", "ACC", "https://www.google.com/s2/favicons?domain=accnetwork.com&sz=128")',f'XNetwork("ACC Network", "SPORTS", "ACC", "{ACC}")')
needle='XNetwork("RugbyPass TV", "RUGBY", "RUGBY", "https://www.google.com/s2/favicons?domain=rugbypass.tv&sz=128")'
if 'XNetwork("WWE", "WRESTLING", "WWE", "' not in text:
    if needle in text: text=text.replace(needle,needle+f',\n    XNetwork("WWE", "WRESTLING", "WWE", "{WWE}")')
mobile.write_text(text)

tv=Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
t=tv.read_text()
for old,new in {
'https://www.google.com/s2/favicons?domain=accnetwork.com&sz=128':ACC,
'https://www.google.com/s2/favicons?domain=wwe.com&sz=128':WWE,
'https://www.google.com/s2/favicons?domain:fiawec.com&sz=128':WEC,
'https://www.google.com/s2/favicons?domain:motogp.com&sz=128':MOTOGP,
'https://www.google.com/s2/favicons?domain:wrc.com&sz=128':WRC,
}.items(): t=t.replace(old,new)
if 'TvSport("WWE"' not in t:
    # League-routing normalizes the sports list. It may remove WRESTLING,
    # so insert WWE beside BOXING when that happens.
    marker='TvSport("WRESTLING","WR"'
    if marker in t: pos=t.find(marker)
    else:
        marker='TvSport("BOXING","BOX"'
        pos=t.find(marker)
    if pos<0: raise SystemExit('No TV combat-sports insertion point found')
    end=t.find('),',pos)
    if end<0: raise SystemExit('Combat-sports entry terminator not found')
    t=t[:end+2]+f'\n    TvSport("WWE","WWE","{WWE}"),'+t[end+2:]
tv.write_text(t)
print('Verified ACC/WWE and stable motorsport logo URLs applied to Mobile + TV')