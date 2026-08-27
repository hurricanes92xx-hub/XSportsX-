from pathlib import Path
import re

TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
FUTURE_MAIN = Path("app/src/main/java/com/xsportsx/app/MainActivityFuture.kt")

def tv_patch():
    text = TV.read_text()
    if 'private data class TvSport(val name:String,val glyph:String,val logoUrl:String)' not in text:
        text = text.replace('private data class TvSport(val name:String,val glyph:String)', 'private data class TvSport(val name:String,val glyph:String,val logoUrl:String)')
    if 'private data class TvNetwork(val name:String,val mark:String,val logoUrl:String)' not in text:
        text = text.replace('private data class TvNetwork(val name:String,val mark:String)', 'private data class TvNetwork(val name:String,val mark:String,val logoUrl:String)')
    sports='''private val tvSports = listOf(
    TvSport("NFL","NFL","https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"),TvSport("NBA","NBA","https://a.espncdn.com/i/teamlogos/leagues/500/nba.png"),
    TvSport("NCAA FB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaaf.png"),TvSport("NCAA BB","NCAA","https://a.espncdn.com/i/teamlogos/leagues/500/ncaab.png"),
    TvSport("NCAA VB","NCAA",""),TvSport("MLB","MLB","https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"),TvSport("NHL","NHL","https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png"),
    TvSport("UFC","UFC",""),TvSport("BOXING","BOX",""),TvSport("RUGBY","RUGBY",""),TvSport("VOLLEYBALL","VB",""),TvSport("LACROSSE","LAX",""),TvSport("WRESTLING","WR",""),
    TvSport("FORMULA 1","F1",""),TvSport("NASCAR","NASCAR",""),TvSport("DTM","DTM",""),TvSport("MOTOGP","MotoGP",""),TvSport("WRC","WRC",""),TvSport("WEC","WEC",""),TvSport("FORMULA E","FE",""),TvSport("MXGP","MXGP",""),TvSport("MONSTER JAM","MJ",""),TvSport("SOCCER","SOCCER","")
)'''
    text, sports_count = re.subn(r'private val tvSports = listOf\(.*?\nprivate val tvNetworks', sports + '\nprivate val tvNetworks', text, count=1, flags=re.S)
    if sports_count != 1:
        raise SystemExit('Could not locate tvSports catalog')
    networks='''private val tvNetworks = listOf(
    TvNetwork("ESPN","ESPN",""),TvNetwork("ESPN2","ESPN2",""),TvNetwork("ESPNU","ESPNU",""),TvNetwork("NFL NETWORK","NFL",""),TvNetwork("FS1","FS1",""),TvNetwork("CBS SPORTS","CBS",""),TvNetwork("SEC NETWORK","SEC",""),TvNetwork("ACC NETWORK","ACC",""),TvNetwork("BIG TEN NETWORK","B1G",""),TvNetwork("ESPN+","ESPN+",""),TvNetwork("PAC-12 NETWORK","PAC12",""),TvNetwork("NBA TV","NBA TV",""),TvNetwork("MLB NETWORK","MLB",""),TvNetwork("NHL NETWORK","NHL",""),TvNetwork("UFC FIGHT PASS","UFC",""),TvNetwork("RED BULL TV","RED BULL",""),TvNetwork("MONSTER JAM","MJ",""),TvNetwork("RUGBYPASS TV","RUGBY","")
)'''
    text, network_count = re.subn(r'private val tvNetworks = listOf\(.*?\nprivate fun dateRange', networks + '\nprivate fun dateRange', text, count=1, flags=re.S)
    if network_count != 1:
        raise SystemExit('Could not locate tvNetworks catalog')
    text=text.replace('TvSection("SPORTS NETWORKS","LIVE SOURCES")','TvSection("NETWORKS","LIVE SOURCES")')
    text=text.replace('@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvTile(it.name,it.glyph,TvBlue){onNetwork(it.name)}}}}','@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvBadgeTile(it,onNetwork)}}}')
    text=text.replace('@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){Column(verticalArrangement=Arrangement.spacedBy(8.dp)){networks.chunked(5).forEach{row->Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()){row.forEach{network->TvTile(network.name,network.mark,TvRed){onNetwork(network.name)}}}}}}','@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(networks,key={it.name}){network->TvNetworkTile(network,onNetwork)}}}')
    if 'private fun TvBadgeTile' not in text:
        anchor='@Composable private fun TvTile(title:String,mark:String,accent:Color,onClick:()->Unit){'
        if anchor not in text: raise SystemExit('TvTile anchor not found')
        components='''@Composable private fun TvHardwiredLogo(label:String,size:androidx.compose.ui.unit.Dp=62.dp){val k=label.uppercase();val bg=when{ k.contains("ESPN")->Color(0xFFE31837);k.contains("SEC")->Color(0xFF174A7E);k.contains("ACC")->Color(0xFF0077B8);k.contains("B1G")||k.contains("BIG TEN")->Color(0xFF111923);k.contains("NFL")->Color(0xFF013369);k.contains("NBA")->Color(0xFF17408B);k.contains("MLB")->Color(0xFF0B4F8A);k.contains("NHL")->Color(0xFF111923);k.contains("FS1")->Color(0xFF0877BD);k.contains("CBS")->Color(0xFF1D5B89);k.contains("UFC")->Color(0xFFD20A0A);k.contains("FORMULA 1")->Color(0xFFE10600);k.contains("NASCAR")->Color(0xFF101318);k.contains("DTM")->Color(0xFF28384A);k.contains("MOTOGP")->Color(0xFFDF102D);k.contains("WRC")->Color(0xFF00A651);k.contains("WEC")->Color(0xFF1D5CA8);k.contains("RUGBY")->Color(0xFFE30613);k.contains("MONSTER")->Color(0xFF161616);k.contains("RED BULL")->Color(0xFF0A1B4A);else->Color(0xFF202A38)};Box(Modifier.size(size).clip(RoundedCornerShape(size/3)).background(bg),contentAlignment=Alignment.Center){Text(label.replace(" NETWORK","").replace(" SPORTS",""),color=Color.White,fontSize=if(label.length>7)8.sp else 12.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable private fun TvLogo(url:String,label:String,size:androidx.compose.ui.unit.Dp){var failed by remember(url){mutableStateOf(false)};if(url.isNotBlank()&&!failed)AsyncImage(model=url,contentDescription=label,modifier=Modifier.size(size),contentScale=ContentScale.Fit,onError={failed=true})else TvHardwiredLogo(label,size)}
@Composable private fun TvBadgeTile(sport:TvSport,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(118.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork("LEAGUE:"+sport.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){Box(Modifier.weight(1f),contentAlignment=Alignment.Center){TvLogo(sport.logoUrl,sport.name,70.dp)};Text(sport.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)}}
@Composable private fun TvNetworkTile(network:TvNetwork,onNetwork:(String)->Unit){var focused by remember{mutableStateOf(false)};Column(Modifier.width(142.dp).height(96.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(network.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){TvLogo(network.logoUrl,network.name,42.dp);Spacer(Modifier.height(6.dp));Text(network.name,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)}}
'''
        text=text.replace(anchor,components+anchor,1)
    TV.write_text(text)

def mobile_patch():
    if not MOBILE.exists(): return
    text=MOBILE.read_text()
    text=text.replace('MobileSectionLabel("FREE SPORTS SOURCES", null)','MobileSectionLabel("NETWORKS", null)')
    text=text.replace('SportBadgeCard(sport) { onConnect() }','SportBadgeCard(sport) { onNetwork(XNetwork(sport.name, "LEAGUE", sport.icon, sport.logoUrl)) }')
    MOBILE.write_text(text)

def future_main_patch():
    if not FUTURE_MAIN.exists(): return
    text=FUTURE_MAIN.read_text()
    text=text.replace('''var schedules by remember { mutableStateOf(false) }''','''var schedules by remember { mutableStateOf(false) }
            var selectedScheduleLeague by remember { mutableStateOf<String?>(null) }''')
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
    FUTURE_MAIN.write_text(text)

tv_patch();mobile_patch();future_main_patch();print('Sports/network UI patch applied; top sport tiles now route to their matching league schedules on mobile and TV.')
