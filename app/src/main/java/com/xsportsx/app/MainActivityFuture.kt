package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*

class MainActivityFuture : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var connectSource by remember { mutableStateOf(false) }
            var liveFilter by remember { mutableStateOf<String?>(null) }
            var schedules by remember { mutableStateOf(false) }
            var sourceVersion by remember { mutableIntStateOf(0) }
            val connected = remember(sourceVersion) { SourceStore(this@MainActivityFuture).load().isConfigured() }
            when {
                connectSource -> SourceConnectScreen(onBack = { connectSource = false }, onSaved = { sourceVersion++; connectSource = false })
                schedules -> SportsScheduleScreen(onBack = { schedules = false }, onEvent = { event -> liveFilter = listOf(event.home, event.away, event.broadcast).filter { it.isNotBlank() }.joinToString("||"); schedules = false })
                liveFilter != null -> LiveChannelsScreen(filter = liveFilter, onBack = { liveFilter = null })
                else -> key(sourceVersion) {
                    FuturisticHome(
                        onConnect = { if (connected) schedules = true else connectSource = true },
                        onNetwork = { network -> if (connected) liveFilter = network.name else connectSource = true }
                    )
                }
            }
        }
    }
}
