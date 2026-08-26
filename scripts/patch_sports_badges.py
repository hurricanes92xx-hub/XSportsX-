from pathlib import Path

path = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
text = path.read_text()

replacements = {
    'private data class TvSport(val name:String,val glyph:String)': 'private data class TvSport(val name:String,val glyph:String,val logoUrl:String)',
    'private data class TvNetwork(val name:String,val mark:String)': 'private data class TvNetwork(val name:String,val mark:String,val logoUrl:String)',
    'private val tvSports = listOf(TvSport("NFL","NFL"),TvSport("NBA","NBA"),TvSport("NCAA FB","NCAA"),TvSport("NCAA BB","NCAA"),TvSport("MLB","MLB"),TvSport("NHL","NHL"),TvSport("UFC","UFC"),TvSport("BOXING","BOX"))': '''private val tvSports = listOf(
    TvSport("NFL","NFL","https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"),
    TvSport("NBA","NBA","https://a.espncdn.com/i/teamlogos/leagues/500/nba.png"),
    TvSport("NCAA FB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png"),
    TvSport("NCAA BB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),
    TvSport("MLB","MLB","https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"),
    TvSport("NHL","NHL","https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png"),
    TvSport("UFC","UFC","https://www.google.com/s2/favicons?domain=ufc.com&sz=128"),
    TvSport("BOXING","BOX","https://www.google.com/s2/favicons?domain=espn.com&sz=128")
)''',
    'private val tvNetworks = listOf(TvNetwork("ESPN","ESPN"),TvNetwork("ESPN2","ESPN2"),TvNetwork("ESPNU","ESPNU"),TvNetwork("NFL NETWORK","NFL"),TvNetwork("FS1","FS1"),TvNetwork("CBS SPORTS","CBS"),TvNetwork("SEC NETWORK","SEC"),TvNetwork("ACC NETWORK","ACC"),TvNetwork("BIG TEN NETWORK","B1G"),TvNetwork("ESPN+","ESPN+"))': '''private val tvNetworks = listOf(
    TvNetwork("ESPN","ESPN","https://www.google.com/s2/favicons?domain=espn.com&sz=128"),
    TvNetwork("ESPN2","ESPN2","https://www.google.com/s2/favicons?domain=espn.com&sz=128"),
    TvNetwork("ESPNU","ESPNU","https://www.google.com/s2/favicons?domain=espn.com&sz=128"),
    TvNetwork("NFL NETWORK","NFL","https://www.google.com/s2/favicons?domain=nfl.com&sz=128"),
    TvNetwork("FS1","FS1","https://www.google.com/s2/favicons?domain=foxsports.com&sz=128"),
    TvNetwork("CBS SPORTS","CBS","https://www.google.com/s2/favicons?domain=cbssports.com&sz=128"),
    TvNetwork("SEC NETWORK","SEC","https://www.google.com/s2/favicons?domain=secnetwork.com&sz=128"),
    TvNetwork("ACC NETWORK","ACC","https://www.google.com/s2/favicons?domain=accnetwork.com&sz=128"),
    TvNetwork("BIG TEN NETWORK","B1G","https://www.google.com/s2/favicons?domain=btn.com&sz=128"),
    TvNetwork("ESPN+","ESPN+","https://www.google.com/s2/favicons?domain=espn.com&sz=128"),
    TvNetwork("PAC-12 NETWORK","PAC12","https://www.google.com/s2/favicons?domain=pac-12.com&sz=128")
)''',
    'TvSection("SPORTS NETWORKS","LIVE SOURCES");TvNetworkGrid(tvNetworks,onNetwork)': 'TvSection("NETWORKS","LIVE SOURCES");TvNetworkGrid(tvNetworks,onNetwork)',
    '@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvTile(it.name,it.glyph,TvBlue){onNetwork(it.name)}}}}': '@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvBadgeTile(it,onNetwork)}}}',
    '@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){Column(verticalArrangement=Arrangement.spacedBy(8.dp)){networks.chunked(5).forEach{row->Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()){row.forEach{network->TvTile(network.name,network.mark,TvRed){onNetwork(network.name)}}}}}}': '@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(networks,key={it.name}){network->TvNetworkTile(network,onNetwork)}}}',
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"Expected TV source pattern not found: {old[:90]}")
    text = text.replace(old, new, 1)

needle = '@Composable private fun TvTile(title:String,mark:String,accent:Color,onClick:()->Unit){'
if needle not in text:
    raise SystemExit("TvTile anchor not found")

components = '''@Composable private fun TvBadgeTile(sport:TvSport,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(118.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(sport.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){AsyncImage(model=sport.logoUrl,contentDescription=sport.name,modifier=Modifier.size(70.dp).weight(1f),contentScale=ContentScale.Fit);Text(sport.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable private fun TvNetworkTile(network:TvNetwork,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(96.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(network.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){AsyncImage(model=network.logoUrl,contentDescription=network.name,modifier=Modifier.size(42.dp),contentScale=ContentScale.Fit);Spacer(Modifier.height(6.dp));Text(network.name,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)}}
'''
text = text.replace(needle, components + needle, 1)

# Expanded sports: appended to the same runtime list so the existing build step
# remains the single source of truth for the production UI.
expanded = [
    ("RUGBY","RUGBY","rugbypass.tv"),("VOLLEYBALL","VB","volleyballworld.com"),("LACROSSE","LAX","usalacrosse.com"),("WRESTLING","WR","uww.org"),
    ("JUDO","JUDO","ijf.org"),("TAEKWONDO","TKD","worldtaekwondo.org"),("SWIMMING","SWIM","worldaquatics.com"),("DIVING","DIVE","worldaquatics.com"),
    ("WATER POLO","WP","worldaquatics.com"),("GYMNASTICS","GYM","gymnastics.sport"),("CYCLING","BIKE","uci.org"),("DARTS","DARTS","pdc.tv"),
    ("SNOOKER","SNOOKER","wpbsa.com"),("ARCHERY","ARCH","worldarchery.sport"),("EQUESTRIAN","HORSE","fei.org"),
    ("MOTORSPORTS","MOTO","redbull.com"),("FORMULA 1","F1","formula1.com"),("NASCAR","NASCAR","nascar.com"),("INDYCAR","INDY","indycar.com"),
    ("MOTOGP","MotoGP","motogp.com"),("WRC","WRC","wrc.com"),("WEC","WEC","fiawec.com"),("IMSA","IMSA","imsa.com"),
    ("FORMULA E","FE","fiaformulae.com"),("DTM","DTM","dtm.com"),("MXGP","MXGP","mxgp.com"),("MONSTER JAM","MJ","monsterjam.com"),
    ("ESPORTS","ESPORTS","redbull.com"),("ACTION SPORTS","ACTION","redbull.com"),("HANDBALL","HAND","ihf.info"),
    ("FIELD HOCKEY","FH","fih.ch"),("CRICKET","CRICKET","icc-cricket.com"),("SOCCER","SOCCER","fifa.com")
]
marker = 'private val tvSports = listOf('
start = text.find(marker)
if start < 0:
    raise SystemExit("Expanded sports anchor not found")
end = text.find('\n)', start)
if end < 0:
    raise SystemExit("Expanded sports list terminator not found")
block = text[start:end]
for name,glyph,domain in expanded:
    if f'TvSport("{name}"' not in block:
        block += f',\n    TvSport("{name}","{glyph}","https://www.google.com/s2/favicons?domain={domain}&sz=128")'
text = text[:start] + block + text[end:]
path.write_text(text)
print(f"Applied sports badge/network UI and verified {len(expanded)} expanded sports")
