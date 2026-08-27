from pathlib import Path
import re

TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
FUTURE_MAIN = Path("app/src/main/java/com/xsportsx/app/MainActivityFuture.kt")

# Logo policy: league/network marks are local Compose primitives. They never depend on
# ESPN CDN/network availability, Coil, HTTP redirects, or an external logo host.
def tv_patch():
    text = TV.read_text(encoding="utf-8")
    text = text.replace('private data class TvSport(val name:String,val glyph:String)', 'private data class TvSport(val name:String,val glyph:String,val logoUrl:String)')
    text = text.replace('private data class TvNetwork(val name:String,val mark:String)', 'private data class TvNetwork(val name:String,val mark:String,val logoUrl:String)')
    sports = '''private val tvSports = listOf(
    TvSport("NFL","NFL",""),TvSport("NBA","NBA",""),TvSport("NCAA FB","NCAA",""),TvSport("NCAA BB","NCAA",""),TvSport("NCAA VB","NCAA",""),TvSport("MLB","MLB",""),TvSport("NHL","NHL",""),
    TvSport("UFC","UFC",""),TvSport("BOXING","BOX",""),TvSport("RUGBY","RUGBY",""),TvSport("VOLLEYBALL","VB",""),TvSport("LACROSSE","LAX",""),TvSport("WRESTLING","WR",""),
    TvSport("FORMULA 1","F1",""),TvSport("NASCAR","NASCAR",""),TvSport("DTM","DTM",""),TvSport("MOTOGP","MotoGP",""),TvSport("WRC","WRC",""),TvSport("WEC","WEC",""),TvSport("FORMULA E","FE",""),TvSport("MXGP","MXGP",""),TvSport("MONSTER JAM","MJ",""),TvSport("SOCCER","SOCCER","")
)'''
    text, n = re.subn(r'private val tvSports = listOf\(.*?\nprivate val tvNetworks', sports + '\nprivate val tvNetworks', text, count=1, flags=re.S)
    if n != 1: raise SystemExit('Could not locate tvSports catalog')
    networks = '''private val tvNetworks = listOf(
    TvNetwork("ESPN","ESPN",""),TvNetwork("ESPN2","ESPN2",""),TvNetwork("ESPNU","ESPNU",""),TvNetwork("NFL NETWORK","NFL",""),TvNetwork("FS1","FS1",""),TvNetwork("CBS SPORTS","CBS",""),TvNetwork("SEC NETWORK","SEC",""),TvNetwork("ACC NETWORK","ACC",""),TvNetwork("BIG TEN NETWORK","B1G",""),TvNetwork("ESPN+","ESPN+",""),TvNetwork("PAC-12 NETWORK","PAC12",""),TvNetwork("NBA TV","NBA TV",""),TvNetwork("MLB NETWORK","MLB",""),TvNetwork("NHL NETWORK","NHL",""),TvNetwork("UFC FIGHT PASS","UFC",""),TvNetwork("RED BULL TV","RED BULL",""),TvNetwork("MONSTER JAM","MJ",""),TvNetwork("RUGBYPASS TV","RUGBY","")
)'''
    text, n = re.subn(r'private val tvNetworks = listOf\(.*?\nprivate fun dateRange', networks + '\nprivate fun dateRange', text, count=1, flags=re.S)
    if n != 1: raise SystemExit('Could not locate tvNetworks catalog')
    text = text.replace('TvSection("SPORTS NETWORKS","LIVE SOURCES")', 'TvSection("NETWORKS","LIVE SOURCES")')
    old_sport = '@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvTile(it.name,it.glyph,TvBlue){onNetwork(it.name)}}}}'
    new_sport = '''@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){sport->TvBadgeTile(sport,onNetwork)}}}'''
    text = text.replace(old_sport, new_sport, 1)
    old_net = '@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){Column(verticalArrangement=Arrangement.spacedBy(8.dp)){networks.chunked(5).forEach{row->Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()){row.forEach{network->TvTile(network.name,network.mark,TvRed){onNetwork(network.name)}}}}}}'
    new_net = '''@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(networks,key={it.name}){network->TvNetworkTile(network,onNetwork)}}}'''
    text = text.replace(old_net, new_net, 1)
    if 'private fun TvBadgeTile' not in text:
        components='''@Composable private fun TvBadgeTile(sport:TvSport,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(118.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork("LEAGUE:"+sport.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){Box(Modifier.weight(1f),contentAlignment=Alignment.Center){XSportsLeagueLogo(sport.name,Modifier,size=70.dp)};Text(sport.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable private fun TvNetworkTile(network:TvNetwork,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(96.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(network.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){XSportsNetworkLogo(network.name,Modifier,size=42.dp);Spacer(Modifier.height(6.dp));Text(network.name,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)}}
'''
        anchor = '@Composable private fun TvNav('
        if anchor not in text: raise SystemExit('Stable TV composable anchor not found')
        text = text.replace(anchor, components + anchor, 1)
    TV.write_text(text, encoding="utf-8")

def mobile_patch():
    if not MOBILE.exists(): return
    text=MOBILE.read_text(encoding="utf-8")
    text=text.replace('MobileSectionLabel("FREE SPORTS SOURCES", null)', 'MobileSectionLabel("NETWORKS", null)')
    text=text.replace('SportBadgeCard(sport) { onConnect() }', 'SportBadgeCard(sport) { onNetwork(XNetwork(sport.name, "LEAGUE", sport.icon, sport.logoUrl)) }')
    text = re.sub(r'@Composable private fun BadgeImage\(url:String,fallback:String,modifier:Modifier=Modifier\)\{.*?\n\}', '@Composable private fun BadgeImage(url:String,fallback:String,modifier:Modifier=Modifier){XSportsLeagueLogo(fallback,modifier,size=72.dp)}', text, count=1, flags=re.S)
    text = re.sub(r'"https://a\.espncdn\.com/i/teamlogos/leagues/500/[^\"]+"', '""', text)
    MOBILE.write_text(text, encoding="utf-8")

def future_main_patch():
    if not FUTURE_MAIN.exists(): return
    text=FUTURE_MAIN.read_text(encoding="utf-8")
    if 'var selectedScheduleLeague by remember { mutableStateOf<String?>(null) }' not in text:
        text=text.replace('''var schedules by remember { mutableStateOf(false) }''','''var schedules by remember { mutableStateOf(false) }\n            var selectedScheduleLeague by remember { mutableStateOf<String?>(null) }''',1)
    text=text.replace('''TvAdaptiveHost(
                    onConnect = { tvConnectChooser = true },
                    onNetwork = { network -> selectedEvent = null; liveFilter = network }
                )''','''TvAdaptiveHost(
                    onConnect = { tvConnectChooser = true },
                    onNetwork = { network ->
                        if (network.startsWith("LEAGUE:")) {
                            selectedScheduleLeague = network.removePrefix("LEAGUE:")
                            schedules = true
                        } else {
                            selectedEvent = null
                            liveFilter = network
                        }
                    }
                )''')
    text=text.replace('''FuturisticHome(onConnect = { if (connected) schedules = true else connectSource = true }, onNetwork = { network -> selectedEvent = null; liveFilter = network.name })''','''FuturisticHome(
                            onConnect = { if (connected) schedules = true else connectSource = true },
                            onNetwork = { network ->
                                if (network.type == "LEAGUE") {
                                    selectedScheduleLeague = network.name
                                    schedules = true
                                } else {
                                    selectedEvent = null
                                    liveFilter = network.name
                                }
                            }
                        )''')
    text=text.replace('''SportsScheduleScreen(onBack = { schedules = false }, onEvent = { event -> selectedEvent = event; liveFilter = null; schedules = false })''','''SportsScheduleScreen(initialLeague = selectedScheduleLeague, onBack = { schedules = false }, onEvent = { event -> selectedEvent = event; liveFilter = null; schedules = false })''')
    FUTURE_MAIN.write_text(text, encoding="utf-8")

tv_patch(); mobile_patch(); future_main_patch(); print('Local league/network logo patch applied.')
