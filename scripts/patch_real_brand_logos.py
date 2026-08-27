import re
from pathlib import Path

TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")

# Keep legacy static ESPN CDN logo URLs out of the production UI. Static cards
# use the bundled renderer; live/source URLs remain untouched elsewhere.
for target in (TV, MOBILE):
    if target.exists():
        source = target.read_text()
        cleaned = re.sub(r'https://a\\.espncdn\\.com/i/teamlogos/leagues[^\"]*', '', source)
        if cleaned != source:
            target.write_text(cleaned)
            print(f"Removed legacy ESPN CDN league logo URLs from {target}")

text = TV.read_text()

# patch_sports_badges.py may already have installed the shared TV badge/grid.
# Treat that state as success instead of trying to replace an older source shape.
if "XSportsLeagueLogo" in text and "XSportsNetworkLogo" in text:
    print("TV already uses bundled league/network logo renderer")
    raise SystemExit(0)

old_sport = '@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){items(sports,key={it.name}){TvTile(it.name,it.glyph,TvBlue){onNetwork(it.name)}}}}'
new_sport = '''@Composable private fun TvSportRow(sports:List<TvSport>,onNetwork:(String)->Unit){
    LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){
        items(sports,key={it.name}){sport->
            var focused by remember{mutableStateOf(false)}
            Column(Modifier.width(142.dp).height(118.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvBlue.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork("LEAGUE:"+sport.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
                Box(Modifier.weight(1f),contentAlignment=Alignment.Center){XSportsLeagueLogo(sport.name,Modifier,size=70.dp)}
                Text(sport.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)
            }
        }
    }
}'''
if old_sport not in text:
    raise SystemExit("TvSportRow source changed; refusing unsafe replacement")
text = text.replace(old_sport, new_sport, 1)

old_net = '@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){Column(verticalArrangement=Arrangement.spacedBy(8.dp)){networks.chunked(5).forEach{row->Row(horizontalArrangement=Arrangement.spacedBy(8.dp),modifier=Modifier.fillMaxWidth()){row.forEach{network->TvTile(network.name,network.mark,TvRed){onNetwork(network.name)}}}}}}'
new_net = '''@Composable private fun TvNetworkGrid(networks:List<TvNetwork>,onNetwork:(String)->Unit){
    LazyRow(horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=4.dp)){
        items(networks,key={it.name}){network->
            var focused by remember{mutableStateOf(false)}
            Column(Modifier.width(142.dp).height(96.dp).clip(RoundedCornerShape(16.dp)).background(TvPanel).border(1.dp,TvRed.copy(alpha=if(focused)1f else .25f),RoundedCornerShape(16.dp)).onFocusChanged{focused=it.isFocused}.focusable().clickable{onNetwork(network.name)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
                XSportsNetworkLogo(network.name,Modifier,size=44.dp)
                Spacer(Modifier.height(6.dp))
                Text(network.name,color=Color.White,fontSize=9.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
            }
        }
    }
}'''
if old_net not in text:
    raise SystemExit("TvNetworkGrid source changed; refusing unsafe replacement")
text = text.replace(old_net, new_net, 1)
TV.write_text(text)
print("TV sport/network cards now use bundled logo renderer")
