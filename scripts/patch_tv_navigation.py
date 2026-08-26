from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
s = p.read_text(encoding="utf-8")

# Top-bar Settings must navigate to the real Settings screen instead of invoking the source connector.
s = s.replace(
    'var loadingUpcoming by remember { mutableStateOf(false) }\n    val scroll = rememberScrollState()',
    'var loadingUpcoming by remember { mutableStateOf(false) }\n    var tvModeEnabled by remember { mutableStateOf(false) }\n    val scroll = rememberScrollState()',
    1,
)
s = s.replace('TvTopBar(onConnect)', 'TvTopBar(onSettings = { selectedNav = "SETTINGS" }, tvModeEnabled = tvModeEnabled, onToggleTvMode = { tvModeEnabled = !tvModeEnabled })', 1)

# Make the TV MODE label a real, focusable/clickable control and Settings a real navigation button.
pattern = re.compile(r'@Composable private fun TvTopBar\(.*?(?=\n@Composable)', re.S)
replacement = '''@Composable private fun TvTopBar(\n    onSettings: () -> Unit,\n    tvModeEnabled: Boolean,\n    onToggleTvMode: () -> Unit\n) {\n    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {\n        Text("XSPORTSX", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)\n        Spacer(Modifier.weight(1f))\n        Text("LIVE SPORTS", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Black)\n        Spacer(Modifier.width(18.dp))\n        TvActionButton("⚙  Settings", onSettings)\n        Spacer(Modifier.width(12.dp))\n        TvModeButton(tvModeEnabled, onToggleTvMode)\n    }\n}\n\n@Composable private fun TvActionButton(text: String, onClick: () -> Unit) {\n    var focused by remember { mutableStateOf(false) }\n    Box(\n        Modifier.clip(RoundedCornerShape(14.dp))\n            .background(if (focused) Color(0xFF241018) else Color.Transparent)\n            .border(1.dp, TvRed.copy(alpha = if (focused) 1f else .35f), RoundedCornerShape(14.dp))\n            .onFocusChanged { focused = it.isFocused }\n            .focusable()\n            .clickable { onClick() }\n            .padding(horizontal = 14.dp, vertical = 9.dp)\n    ) {\n        Text(text, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black)\n    }\n}\n\n@Composable private fun TvModeButton(enabled: Boolean, onClick: () -> Unit) {\n    var focused by remember { mutableStateOf(false) }\n    Box(\n        Modifier.clip(RoundedCornerShape(14.dp))\n            .background(if (enabled || focused) Color(0xFF10213A) else Color.Transparent)\n            .border(1.dp, TvBlue.copy(alpha = if (enabled || focused) 1f else .35f), RoundedCornerShape(14.dp))\n            .onFocusChanged { focused = it.isFocused }\n            .focusable()\n            .clickable { onClick() }\n            .padding(horizontal = 14.dp, vertical = 9.dp)\n    ) {\n        Text(if (enabled) "TV MODE  ON" else "TV MODE", color = if (enabled) Color(0xFF64B5FF) else Color.White, fontSize = 10.sp, fontWeight = FontWeight.Black)\n    }\n}\n'''
s, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit("Could not locate TvTopBar block")

# The bottom TV MODE label in the navigation rail is also made an actual control.
s = s.replace(
    'Spacer(Modifier.weight(1f))\n        Text("TV MODE", color = Color(0xFF596371), fontSize = 10.sp, fontWeight = FontWeight.Bold)',
    '''Spacer(Modifier.weight(1f))\n        var modeFocused by remember { mutableStateOf(false) }\n        Row(\n            Modifier.clip(RoundedCornerShape(12.dp))\n                .background(if (modeFocused) Color(0xFF10213A) else Color.Transparent)\n                .border(1.dp, TvBlue.copy(alpha = if (modeFocused) 1f else .25f), RoundedCornerShape(12.dp))\n                .onFocusChanged { modeFocused = it.isFocused }\n                .focusable()\n                .clickable { /* TV mode is controlled from the top-bar button. */ }\n                .padding(horizontal = 10.dp, vertical = 7.dp)\n        ) {\n            Text("TV MODE", color = if (modeFocused) Color(0xFF64B5FF) else Color(0xFF8993A2), fontSize = 10.sp, fontWeight = FontWeight.Black)\n        }''',
    1,
)

p.write_text(s, encoding="utf-8")
print("TV navigation patch applied")
