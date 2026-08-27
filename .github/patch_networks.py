from pathlib import Path

# Network logos must never depend on a remote image host. Patch the production
# screens to use the shared local XSportsNetworkLogo renderer.
mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
ms = mobile.read_text()
start = ms.index('@Composable private fun NetworkCard(')
end = ms.index('\n@Composable private fun UpcomingStrip()', start)
ms = ms[:start] + '''@Composable private fun NetworkCard(network:XNetwork,onClick:(XNetwork)->Unit){
    Column(Modifier.width(132.dp).height(132.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable{onClick(network)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
        Box(Modifier.fillMaxWidth().height(72.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF0A0F17)),contentAlignment=Alignment.Center){XSportsNetworkLogo(network.name,Modifier,size=56.dp)}
        Spacer(Modifier.height(7.dp))
        Text(network.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}'''+ms[end:]
mobile.write_text(ms)

tv = Path('app/src/main/java/com/xsportsx/app/TvHome.kt')
ts = tv.read_text()
old = '''@Composable private fun TvNetworkCard(network:TvNetwork,onClick:()->Unit) { var focused by remember { mutableStateOf(false) }; Column(Modifier.width(108.dp).height(72.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { TvSportMark(network.mark, 30.dp, focused); Text(network.name, color = TvMuted, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }'''
new = '''@Composable private fun TvNetworkCard(network:TvNetwork,onClick:()->Unit) {
    var focused by remember { mutableStateOf(false) }
    Column(Modifier.width(108.dp).height(86.dp).clip(RoundedCornerShape(11.dp)).background(TvPanel).border(1.5.dp, TvBlue.copy(alpha = if (focused) 1f else .16f), RoundedCornerShape(11.dp)).onFocusChanged { focused = it.isFocused }.focusable().clickable { onClick() }, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        XSportsNetworkLogo(network.name, Modifier, 42.dp)
        Spacer(Modifier.height(5.dp))
        Text(network.name, color = Color.White, fontSize = 7.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}'''
if old in ts:
    ts = ts.replace(old, new, 1)
else:
    print('TvNetworkCard signature already changed; leaving it intact')
tv.write_text(ts)
print('Network cards now use the shared local logo renderer on mobile and TV.')
