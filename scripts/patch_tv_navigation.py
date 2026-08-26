from pathlib import Path
import re

p = Path("app/src/main/java/com/xsportsx/app/TvHome.kt")
if not p.is_file():
    raise SystemExit(f"Missing TV source: {p}")

s = p.read_text(encoding="utf-8")

# The TV source is intentionally compacted to one-line Compose declarations, so
# match the actual source shape rather than relying on pretty-printed whitespace.
if "var tvModeEnabled by remember" not in s:
    s, n = re.subn(
        r'(var loadingUpcoming by remember\s*\{\s*mutableStateOf\(false\)\s*\}\s*;)',
        r'\1var tvModeEnabled by remember{mutableStateOf(false)};',
        s,
        count=1,
    )
    if n != 1:
        raise SystemExit("Could not locate loadingUpcoming state")

# Settings already navigates correctly in the current source; convert the call
# to the expanded top-bar API so TV MODE is also a real focusable control.
old_top_call = 'TvTopBar{selectedNav="SETTINGS"}'
new_top_call = 'TvTopBar(onSettings={selectedNav="SETTINGS"},tvModeEnabled=tvModeEnabled,onToggleTvMode={tvModeEnabled=!tvModeEnabled})'
if old_top_call in s:
    s = s.replace(old_top_call, new_top_call, 1)
elif 'TvTopBar(onSettings=' not in s:
    # Handle the spaced form if the formatter changes later.
    s, n = re.subn(
        r'TvTopBar\s*\{\s*selectedNav\s*=\s*"SETTINGS"\s*\}',
        new_top_call,
        s,
        count=1,
    )
    if n != 1:
        raise SystemExit("Could not locate TvTopBar call")

# Replace the existing top bar with Settings + TV MODE controls.
pattern = re.compile(r'@Composable private fun TvTopBar\(.*?(?=\n?@Composable)', re.S)
replacement = '''@Composable private fun TvTopBar(
    onSettings: () -> Unit,
    tvModeEnabled: Boolean,
    onToggleTvMode: () -> Unit
) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text("XSPORTSX", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.weight(1f))
        Text("LIVE SPORTS", color = TvMuted, fontSize = 10.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.width(18.dp))
        TvActionButton("⚙  Settings", onSettings)
        Spacer(Modifier.width(12.dp))
        TvModeButton(tvModeEnabled, onToggleTvMode)
    }
}

@Composable private fun TvActionButton(text: String, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(
        Modifier.clip(RoundedCornerShape(14.dp))
            .background(if (focused) Color(0xFF241018) else Color.Transparent)
            .border(1.dp, TvRed.copy(alpha = if (focused) 1f else .35f), RoundedCornerShape(14.dp))
            .onFocusChanged { focused = it.isFocused }
            .focusable()
            .clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 9.dp)
    ) {
        Text(text, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black)
    }
}

@Composable private fun TvModeButton(enabled: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(
        Modifier.clip(RoundedCornerShape(14.dp))
            .background(if (enabled || focused) Color(0xFF10213A) else Color.Transparent)
            .border(1.dp, TvBlue.copy(alpha = if (enabled || focused) 1f else .35f), RoundedCornerShape(14.dp))
            .onFocusChanged { focused = it.isFocused }
            .focusable()
            .clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 9.dp)
    ) {
        Text(
            if (enabled) "TV MODE  ON" else "TV MODE",
            color = if (enabled) Color(0xFF64B5FF) else Color.White,
            fontSize = 10.sp,
            fontWeight = FontWeight.Black,
        )
    }
}
'''
s, n = pattern.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit("Could not locate TvTopBar block")

# Make the bottom TV MODE label in the navigation rail focusable as well.
old_bottom = 'Spacer(Modifier.weight(1f));Text("TV MODE",color=Color(0xFF596371),fontSize=10.sp,fontWeight=FontWeight.Bold)'
new_bottom = '''Spacer(Modifier.weight(1f));var modeFocused by remember{mutableStateOf(false)};Row(Modifier.clip(RoundedCornerShape(12.dp)).background(if(modeFocused)Color(0xFF10213A)else Color.Transparent).border(1.dp,TvBlue.copy(alpha=if(modeFocused)1f else .25f),RoundedCornerShape(12.dp)).onFocusChanged{modeFocused=it.isFocused}.focusable().clickable{}.padding(horizontal=10.dp,vertical=7.dp)){Text("TV MODE",color=if(modeFocused)Color(0xFF64B5FF)else Color(0xFF8993A2),fontSize=10.sp,fontWeight=FontWeight.Black)}'''
if old_bottom in s:
    s = s.replace(old_bottom, new_bottom, 1)

p.write_text(s, encoding="utf-8")
print("TV navigation patch applied")
