import re
from pathlib import Path

TV = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
MOBILE = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")

for target in (TV, MOBILE):
    if target.exists():
        source = target.read_text(encoding="utf-8")
        # Correctly remove legacy ESPN CDN league-logo URLs while preserving
        # the surrounding Kotlin string/constructor syntax.
        cleaned = re.sub(r'https://a\.espncdn\.com/i/teamlogos/leagues[^\"]*', '', source)
        if cleaned != source:
            target.write_text(cleaned, encoding="utf-8")
            print(f"Removed legacy ESPN CDN league logo URLs from {target}")

if not TV.exists():
    print("TV source absent; nothing to patch")
    raise SystemExit(0)

text = TV.read_text(encoding="utf-8")
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
changed = False
if old_sport in text:
    text = text.replace(old_sport, new_sport, 1)
    changed = True
if old_net in text:
    text = text.replace(old_net, new_net, 1)
    changed = True
if changed:
    TV.write_text(text, encoding="utf-8")
    print("TV legacy sport/network cards upgraded to bundled logo renderer")
else:
    print("No legacy TV card shape matched; preserving current UI for renderer checks")