from pathlib import Path
import re

mobile = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = mobile.read_text()

# Static network cards no longer depend on Google favicon service.
s = re.sub(r'(XNetwork\("[^"]+"\s*,\s*"[^"]+"\s*,\s*"[^"]+"\s*,\s*)"[^"]*"(\))', r'\1""\2', s)
# Static sport cards that currently use Google favicon fall back to a local mark.
s = re.sub(r'(SportVisual\("[^"]+"\s*,\s*"[^"]+"\s*,\s*)"https://www\.google\.com/s2/favicons[^\"]*"(\))', r'\1""\2', s)
s = re.sub(r'https://www\.google\.com/s2/favicons\?domain:[^\"]+', '', s)

locked_logo = '''@Composable private fun LockedLogo(label:String,name:String=label,size:androidx.compose.ui.unit.Dp=62.dp){
    val k=name.uppercase()
    val bg=when{
        k.contains("ESPN")||k.contains("F1") -> Color(0xFFE50920)
        k.contains("SEC") -> Color(0xFF174A7E)
        k.contains("ACC") -> Color(0xFF0066A1)
        k.contains("B1G") -> Color(0xFF151A20)
        k.contains("NFL") -> Color(0xFF013369)
        k.contains("NBA") -> Color(0xFF17408B)
        k.contains("NASCAR") -> Color(0xFF101318)
        k.contains("DTM") -> Color(0xFF28384A)
        k.contains("MONSTER") -> Color(0xFF151515)
        k.contains("RUGBY") -> Color(0xFF0B5E45)
        else -> Color(0xFF202A38)
    }
    Box(Modifier.size(size).clip(RoundedCornerShape(size/3)).background(bg),contentAlignment=Alignment.Center){
        Text(label,color=Color.White,fontSize=if(label.length>6)8.sp else 14.sp,fontWeight=FontWeight.Black,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}

'''
if 'private fun LockedLogo(' not in s:
    s = s.replace('@Composable private fun BadgeImage', locked_logo + '@Composable private fun BadgeImage', 1)

start = s.find('@Composable private fun BadgeImage')
end = s.find('\n\n@Composable\nfun FuturisticHome', start)
if start < 0 or end < 0:
    raise SystemExit('BadgeImage anchors not found')
s = s[:start] + '''@Composable private fun BadgeImage(url:String,fallback:String,modifier:Modifier=Modifier){
    var failed by remember(url){mutableStateOf(false)}
    if(!failed && url.isNotBlank()) AsyncImage(model=url,contentDescription=fallback,modifier=modifier,contentScale=ContentScale.Fit,onError={failed=true})
    else LockedLogo(fallback,fallback,72.dp)
}''' + s[end:]

start = s.find('@Composable private fun NetworkCard')
end = s.find('@Composable private fun BrandPill', start)
if start < 0 or end < 0:
    raise SystemExit('NetworkCard anchors not found')
s = s[:start] + '''@Composable private fun NetworkCard(network:XNetwork,onClick:(XNetwork)->Unit){
    Column(Modifier.width(132.dp).height(124.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable{onClick(network)}.padding(10.dp),horizontalAlignment=Alignment.CenterHorizontally){
        Box(Modifier.fillMaxWidth().height(70.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF0A0F17)),contentAlignment=Alignment.Center){LockedLogo(network.icon,network.name,52.dp)}
        Spacer(Modifier.height(7.dp))
        Text(network.name,color=Color.White,fontSize=10.sp,fontWeight=FontWeight.Bold,maxLines=1,overflow=TextOverflow.Ellipsis)
    }
}
''' + s[end:]
mobile.write_text(s)

# The build-time sports patch must not put Google favicons or SVG-only remote
# assets back into the app on every build.
patcher = Path('scripts/patch_sports_badges.py')
t = patcher.read_text()
t = re.sub(r'"https://www\.google\.com/s2/favicons\?domain=[^\"]+"', '""', t)
t = re.sub(r'"https://commons\.wikimedia\.org/wiki/Special:Redirect/file/[^\"]+"', '""', t)
patcher.write_text(t)
print('Logo lockdown applied')
