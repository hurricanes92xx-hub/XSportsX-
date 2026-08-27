package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private data class LogoPalette(val bg: Color, val fg: Color, val accent: Color)

private fun palette(key: String): LogoPalette = when {
    key.contains("NFL") -> LogoPalette(Color(0xFF0B2A57), Color.White, Color(0xFFC7A64A))
    key == "NBA" -> LogoPalette(Color(0xFF17408B), Color.White, Color(0xFFE31837))
    key.contains("NCAA") -> LogoPalette(Color(0xFF182536), Color.White, Color(0xFFFFB400))
    key == "MLB" -> LogoPalette(Color(0xFF0B3A73), Color.White, Color(0xFFE31837))
    key == "NHL" -> LogoPalette(Color(0xFF151C27), Color.White, Color(0xFFB8C7D9))
    key == "WNBA" -> LogoPalette(Color(0xFF3A164E), Color.White, Color(0xFFF36B21))
    key == "MLS" -> LogoPalette(Color(0xFF1A2738), Color.White, Color(0xFF2E8BFF))
    key == "EPL" -> LogoPalette(Color(0xFF24133E), Color.White, Color(0xFFB889FF))
    key.contains("UFC") -> LogoPalette(Color(0xFF171717), Color.White, Color(0xFFD20A0A))
    key.contains("BOX") -> LogoPalette(Color(0xFF2B1710), Color.White, Color(0xFFFF6D00))
    key.contains("RUGBY") -> LogoPalette(Color(0xFF0B5E45), Color.White, Color(0xFF7BE0B6))
    else -> LogoPalette(Color(0xFF202A38), Color.White, Color(0xFFFF1838))
}

@Composable
fun XSportsLeagueLogo(name: String, modifier: Modifier = Modifier, size: Dp = 72.dp) {
    val key = name.uppercase()
    val p = palette(key)
    val main = when {
        key.contains("NCAA") -> "NCAA"
        key == "FORMULA 1" -> "F1"
        key == "MOTOGP" -> "MotoGP"
        key == "FORMULA E" -> "FE"
        key == "MONSTER JAM" -> "MJ"
        else -> key.replace(" NETWORK", "").take(7)
    }
    val sub = when {
        key == "NCAA FB" -> "FOOTBALL"
        key == "NCAA BB" -> "BASKETBALL"
        key == "NCAA VB" -> "VOLLEYBALL"
        key == "NBA" -> "BASKETBALL"
        key == "MLB" -> "BASEBALL"
        key == "NHL" -> "HOCKEY"
        key == "NFL" -> "FOOTBALL"
        key == "WNBA" -> "BASKETBALL"
        key == "UFC" -> "FIGHT"
        key == "BOXING" -> "BOXING"
        else -> "SPORTS"
    }
    Box(modifier.size(size).clip(RoundedCornerShape(size / 3)).background(p.bg).border(1.dp, p.accent.copy(alpha = .8f), RoundedCornerShape(size / 3)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
            Text(main, color = p.fg, fontSize = if (main.length > 5) 9.sp else 15.sp, fontWeight = FontWeight.Black, letterSpacing = .3.sp, maxLines = 1, textAlign = TextAlign.Center)
            Spacer(Modifier.height(2.dp))
            Box(Modifier.width(size * .52f).height(2.dp).background(p.accent))
            Spacer(Modifier.height(2.dp))
            Text(sub, color = p.fg.copy(alpha = .72f), fontSize = 5.sp, fontWeight = FontWeight.Bold, letterSpacing = .45.sp, maxLines = 1, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun XSportsNetworkLogo(name: String, modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val key = name.uppercase()
    val (label, p) = when {
        key == "ESPN" -> "ESPN" to LogoPalette(Color(0xFF181818), Color.White, Color(0xFFE31837))
        key == "ESPN2" -> "ESPN2" to LogoPalette(Color(0xFF181818), Color.White, Color(0xFFE31837))
        key == "ESPNU" -> "ESPNU" to LogoPalette(Color(0xFF181818), Color.White, Color(0xFFE31837))
        key == "ESPN+" -> "ESPN+" to LogoPalette(Color(0xFF181818), Color.White, Color(0xFFE31837))
        key.contains("NFL") -> "NFL" to LogoPalette(Color(0xFF0B2A57), Color.White, Color(0xFFC7A64A))
        key == "FS1" -> "FS1" to LogoPalette(Color(0xFF0877BD), Color.White, Color(0xFF5ED5FF))
        key.contains("CBS") -> "CBS" to LogoPalette(Color(0xFF123C63), Color.White, Color(0xFF7EC8FF))
        key.contains("SEC") -> "SEC" to LogoPalette(Color(0xFF174A7E), Color.White, Color(0xFFFFB400))
        key.contains("ACC") -> "ACC" to LogoPalette(Color(0xFF0066A1), Color.White, Color(0xFF7DD9FF))
        key.contains("BIG TEN") -> "B1G" to LogoPalette(Color(0xFF151A20), Color.White, Color(0xFF4EA4FF))
        key.contains("PAC-12") -> "PAC-12" to LogoPalette(Color(0xFF182536), Color.White, Color(0xFFB8C7D9))
        key.contains("NBA TV") -> "NBA TV" to LogoPalette(Color(0xFF17408B), Color.White, Color(0xFFE31837))
        key.contains("MLB") -> "MLB" to LogoPalette(Color(0xFF0B3A73), Color.White, Color(0xFFE31837))
        key.contains("NHL") -> "NHL" to LogoPalette(Color(0xFF151C27), Color.White, Color(0xFFB8C7D9))
        key.contains("UFC") -> "UFC" to LogoPalette(Color(0xFF171717), Color.White, Color(0xFFD20A0A))
        key.contains("RED BULL") -> "RED BULL" to LogoPalette(Color(0xFF0A1B4A), Color.White, Color(0xFFE31837))
        key.contains("MONSTER") -> "MONSTER" to LogoPalette(Color(0xFF151515), Color.White, Color(0xFF72FF00))
        key.contains("RUGBY") -> "RUGBY" to LogoPalette(Color(0xFF0B5E45), Color.White, Color(0xFF7BE0B6))
        else -> key.take(8) to palette(key)
    }
    Box(modifier.size(size).clip(RoundedCornerShape(size / 4)).background(p.bg).border(1.dp, p.accent.copy(alpha = .8f), RoundedCornerShape(size / 4)), contentAlignment = Alignment.Center) {
        Text(label, color = p.fg, fontSize = if (label.length > 6) 7.sp else 12.sp, fontWeight = FontWeight.Black, letterSpacing = .25.sp, maxLines = 1, textAlign = TextAlign.Center)
    }
}
