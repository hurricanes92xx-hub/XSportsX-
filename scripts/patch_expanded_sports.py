from pathlib import Path

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
text = path.read_text()
anchor = 'private val tvSports = listOf('
start = text.find(anchor)
if start < 0:
    raise SystemExit('tvSports declaration not found')
end = text.find('\n)', start)
if end < 0:
    raise SystemExit('tvSports list terminator not found')
entries = [
('RUGBY','RUGBY','rugbypass.tv'),('VOLLEYBALL','VB','volleyballworld.com'),('LACROSSE','LAX','usalacrosse.com'),('WRESTLING','WR','uww.org'),('JUDO','JUDO','ijf.org'),('TAEKWONDO','TKD','worldtaekwondo.org'),('SWIMMING','SWIM','worldaquatics.com'),('DIVING','DIVE','worldaquatics.com'),('WATER POLO','WP','worldaquatics.com'),('GYMNASTICS','GYM','gymnastics.sport'),('CYCLING','BIKE','uci.org'),('DARTS','DARTS','pdc.tv'),('SNOOKER','SNOOKER','wpbsa.com'),('ARCHERY','ARCH','worldarchery.sport'),('EQUESTRIAN','HORSE','fei.org'),('MOTORSPORTS','MOTO','redbull.com'),('FORMULA 1','F1','formula1.com'),('NASCAR','NASCAR','nascar.com'),('INDYCAR','INDY','indycar.com'),('MOTOGP','MotoGP','motogp.com'),('WRC','WRC','wrc.com'),('WEC','WEC','fiawec.com'),('IMSA','IMSA','imsa.com'),('FORMULA E','FE','fiaformulae.com'),('DTM','DTM','dtm.com'),('MXGP','MXGP','mxgp.com'),('MONSTER JAM','MJ','monsterjam.com'),('ESPORTS','ESPORTS','redbull.com'),('ACTION SPORTS','ACTION','redbull.com'),('HANDBALL','HAND','ihf.info'),('FIELD HOCKEY','FH','fih.ch'),('CRICKET','CRICKET','icc-cricket.com'),('SOCCER','SOCCER','fifa.com')]
block = text[start:end]
for name,glyph,domain in entries:
    if f'TvSport("{name}"' not in block:
        block += f',\n    TvSport("{name}","{glyph}","https://www.google.com/s2/favicons?domain={domain}&sz=128")'
text = text[:start] + block + text[end:]
path.write_text(text)
print(f'Added/verified {len(entries)} expanded sports badges')
