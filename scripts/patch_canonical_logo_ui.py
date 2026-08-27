from pathlib import Path
import re

logos = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt')
s = logos.read_text()
replacements = {
    '"WRESTLING" -> BrandSpec(Color(0xFF1A1A1A), Color.White, Color(0xFFE31B23), null, "WR")': '"WRESTLING" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE31B23), "wwe", "WWE")',
    '"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), null, "FS1")': '"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), "fs1", "FS1")',
    '"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), null, "SEC")': '"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), "sec", "SEC")',
    '"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), null, "ACC")': '"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), "acc", "ACC")',
}
for old, new in replacements.items():
    s = s.replace(old, new)
logos.write_text(s)

ui = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = ui.read_text()

sport_re = r'@Composable private fun SportBadgeCard\(sport: SportVisual, onClick: \(\) -> Unit\).*?(?=@Composable private fun|\Z)'
sport_fn = '''@Composable private fun SportBadgeCard(sport: SportVisual, onClick: () -> Unit) {
    Column(Modifier.width(118.dp).height(142.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick() }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.fillMaxWidth().height(88.dp), contentAlignment = Alignment.Center) { XSportsLeagueLogo(sport.name, size = 72.dp) }
        Spacer(Modifier.height(5.dp))
        Text(sport.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
'''
s2, n1 = re.subn(sport_re, sport_fn, s, count=1, flags=re.S)
if n1 != 1:
    raise SystemExit('SportBadgeCard function not found')
s = s2

network_re = r'@Composable private fun NetworkCard\(network:XNetwork,onClick:\(XNetwork\)->Unit\).*?(?=@Composable private fun|\Z)'
network_fn = '''@Composable private fun NetworkCard(network:XNetwork,onClick:(XNetwork)->Unit){
    Column(Modifier.width(150.dp).height(142.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick(network) }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.fillMaxWidth().height(88.dp), contentAlignment = Alignment.Center) { XSportsNetworkLogo(network.name, size = 72.dp) }
        Spacer(Modifier.height(5.dp))
        Text(network.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
'''
s2, n2 = re.subn(network_re, network_fn, s, count=1, flags=re.S)
if n2 != 1:
    raise SystemExit('NetworkCard function not found')
ui.write_text(s2)
print('canonical local logo UI patched')
