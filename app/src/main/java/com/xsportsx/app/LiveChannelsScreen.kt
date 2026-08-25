package com.xsportsx.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.draw.clip
import kotlinx.coroutines.launch

@Composable
fun LiveChannelsScreen(filter: String? = null, onBack: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    var streams by remember { mutableStateOf<List<ResolvedStream>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var playerStream by remember { mutableStateOf<ResolvedStream?>(null) }
    fun matches(stream: ResolvedStream, raw: String?): Boolean {
        val terms = raw?.split("||")?.map { it.trim() }?.filter { it.length >= 3 }.orEmpty()
        if (terms.isEmpty()) return true
        val haystack = (stream.name + " " + stream.group).lowercase()
        return terms.any { haystack.contains(it.lowercase()) }
    }
    fun reload() { scope.launch { loading = true; error = null; runCatching { StreamResolver(context).loadLiveStreams() }.onSuccess { all -> streams = all.filter { matches(it, filter) } }.onFailure { error = it.message ?: "Unable to load live streams" }; loading = false } }
    LaunchedEffect(filter) { reload() }
    if (playerStream != null) { NativePlayerScreen(playerStream!!.url, playerStream!!.name) { playerStream = null }; return }
    Column(Modifier.fillMaxSize().background(Color(0xFF05060A))) {
        Row(Modifier.fillMaxWidth().padding(22.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("‹", color = Color.White, fontSize = 36.sp, modifier = Modifier.clickable { onBack() }); Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) { Text(if (filter.isNullOrBlank()) "LIVE CHANNELS" else "GAME STREAMS", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Black); Text("Authorized source streams • ${streams.size} matches", color = Color(0xFF737B89), fontSize = 11.sp) }
            TextButton(onClick = { reload() }) { Text("REFRESH") }
        }
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Color(0xFFFF1744)) }
            error != null -> Box(Modifier.fillMaxSize().padding(30.dp), contentAlignment = Alignment.Center) { Column(horizontalAlignment = Alignment.CenterHorizontally) { Text("SOURCE ERROR", color = Color(0xFFFF536C), fontWeight = FontWeight.Black); Spacer(Modifier.height(8.dp)); Text(error!!, color = Color.White); Spacer(Modifier.height(12.dp)); TextButton(onClick = { reload() }) { Text("RETRY") } } }
            streams.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No matching game channels found", color = Color(0xFF858B98)) }
            else -> LazyColumn(contentPadding = PaddingValues(horizontal = 22.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(streams, key = { it.url }) { stream ->
                    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Color(0xFF10141C)).clickable { playerStream = stream }.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(44.dp).background(Color(0xFF1A202B), RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) { Text("▶", color = Color(0xFFFF1744), fontWeight = FontWeight.Black) }
                        Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f)) { Text(stream.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text(stream.group, color = Color(0xFF777F8C), fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                        Text("WATCH", color = Color(0xFFFF1744), fontSize = 10.sp, fontWeight = FontWeight.Black)
                    }
                }
            }
        }
    }
}
