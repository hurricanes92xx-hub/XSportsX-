#!/usr/bin/env python3
"""Wire bundled XSportsX branding into the Mobile and Android TV card UIs."""
from pathlib import Path

mobile = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
tv = Path("app/src/main/java/com/xsportsx/app/TvHomeUltimate.kt")

m = mobile.read_text(encoding="utf-8")
old_m = m
m = m.replace(
    'LogoOnlyImage(sport.logoUrl,sport.name,Modifier.size(72.dp))',
    'XSportsLeagueLogo(sport.name, Modifier.size(72.dp), 72.dp)'
)
m = m.replace(
    'BadgeImage(network.logoUrl,network.name,Modifier.size(58.dp))',
    'XSportsNetworkLogo(network.name, Modifier.size(58.dp), 58.dp)'
)
if m != old_m:
    mobile.write_text(m, encoding="utf-8")

v = tv.read_text(encoding="utf-8")
old_v = v
v = v.replace(
    'tvUltimateSports.forEach { league -> TvUltimateRailItem(league, false, blue = true) { onNetwork("LEAGUE:$league") } }',
    'tvUltimateSports.forEach { league -> Row(Modifier.fillMaxWidth().clickable { onNetwork("LEAGUE:$league") }.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) { XSportsLeagueLogo(league, Modifier.size(34.dp), 34.dp); Spacer(Modifier.width(8.dp)); Text(league, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }'
)
v = v.replace(
    'items(tvUltimateSports) { league -> Column(Modifier.width(118.dp).height(74.dp).background(TvUltimatePanel, RoundedCornerShape(14.dp)).border(1.dp, TvUltimateBlue.copy(alpha = .28f), RoundedCornerShape(14.dp)).clickable { onNetwork("LEAGUE:$league") }.padding(10.dp), verticalArrangement = Arrangement.Center) { Text(league.take(5).uppercase(), color = TvUltimateBlue, fontSize = 13.sp, fontWeight = FontWeight.Black); Text(league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }',
    'items(tvUltimateSports) { league -> Column(Modifier.width(142.dp).height(106.dp).background(TvUltimatePanel, RoundedCornerShape(14.dp)).border(1.dp, TvUltimateBlue.copy(alpha = .28f), RoundedCornerShape(14.dp)).clickable { onNetwork("LEAGUE:$league") }.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { XSportsLeagueLogo(league, Modifier.size(54.dp), 54.dp); Spacer(Modifier.height(5.dp)); Text(league, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis) } }'
)
v = v.replace(
    'LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(networks) { network -> TvUltimateButton(network) { onNetwork(network) } } }',
    'LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) { items(networks) { network -> Column(Modifier.width(116.dp).height(92.dp).background(TvUltimatePanel, RoundedCornerShape(14.dp)).border(1.dp, TvUltimateRed.copy(alpha = .3f), RoundedCornerShape(14.dp)).clickable { onNetwork(network) }.padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { XSportsNetworkLogo(network, Modifier.size(46.dp), 46.dp); Spacer(Modifier.height(5.dp)); Text(network, color = Color.White, fontSize = 8.sp, fontWeight = FontWeight.Black, maxLines = 1, overflow = TextOverflow.Ellipsis) } } }'
)
if v != old_v:
    tv.write_text(v, encoding="utf-8")

print("Mobile changed:", m != old_m)
print("TV changed:", v != old_v)
