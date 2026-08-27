from pathlib import Path
import re

logos = Path('app/src/main/java/com/xsportsx/app/SportsLogos.kt')
s = logos.read_text()
s = s.replace('"WRESTLING" -> BrandSpec(Color(0xFF1A1A1A), Color.White, Color(0xFFE31B23), null, "WR")', '"WRESTLING" -> BrandSpec(Color(0xFF111111), Color.White, Color(0xFFE31B23), "wwe", "WWE")')
s = s.replace('"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), null, "FS1")', '"FS1" -> BrandSpec(Color(0xFF07101D), Color.White, Color(0xFF2E7DFF), "fs1", "FS1")')
s = s.replace('"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), null, "SEC")', '"SEC NETWORK" -> BrandSpec(Color(0xFF123C2C), Color.White, Color(0xFFFFC72C), "sec", "SEC")')
s = s.replace('"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), null, "ACC")', '"ACC NETWORK" -> BrandSpec(Color(0xFF071A3B), Color.White, Color(0xFF2E8BFF), "acc", "ACC")')
logos.write_text(s)

ui = Path('app/src/main/java/com/xsportsx/app/FuturisticSports.kt')
s = ui.read_text()
s = re.sub(r'@Composable private fun SportBadgeCard\(sport: SportVisual, onClick: \(\) -> Unit\) \{.*?\n\}', '''@Composable private fun SportBadgeCard(sport: SportVisual, onClick: () -> Unit) {
    Column(Modifier.width(118.dp).height(142.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick() }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.fillMaxWidth().height(88.dp), contentAlignment = Alignment.Center) {
            XSportsLeagueLogo(sport.name, size = 72.dp)
        }
        Spacer(Modifier.height(5.dp))
        Text(sport.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}''', s, count=1, flags=re.S)
s = re.sub(r'@Composable private fun NetworkCard\(network:XNetwork,onClick:\(XNetwork\)->Unit\)\{.*?\n\}', '''@Composable private fun NetworkCard(network:XNetwork,onClick:(XNetwork)->Unit){
    Column(Modifier.width(150.dp).height(142.dp).clip(RoundedCornerShape(18.dp)).background(Panel).clickable { onClick(network) }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.fillMaxWidth().height(88.dp), contentAlignment = Alignment.Center) {
            XSportsNetworkLogo(network.name, size = 72.dp)
        }
        Spacer(Modifier.height(5.dp))
        Text(network.name, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}''', s, count=1, flags=re.S)
ui.write_text(s)
print('canonical local logo UI patched')
