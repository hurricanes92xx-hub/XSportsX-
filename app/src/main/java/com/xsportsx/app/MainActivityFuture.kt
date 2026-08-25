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
            var sourceVersion by remember { mutableIntStateOf(0) }
            val connected = remember(sourceVersion) { SourceStore(this@MainActivityFuture).load().isConfigured() }

            when {
                connectSource -> SourceConnectScreen(
                    onBack = { connectSource = false },
                    onSaved = {
                        sourceVersion++
                        connectSource = false
                    }
                )
                liveFilter != null -> LiveChannelsScreen(
                    filter = liveFilter,
                    onBack = { liveFilter = null }
                )
                else -> key(sourceVersion) {
                    FuturisticHome(
                        onConnect = {
                            if (connected) liveFilter = null else connectSource = true
                        },
                        onNetwork = { network ->
                            if (connected) liveFilter = network.name else connectSource = true
                        }
                    )
                }
            }
        }
    }
}
