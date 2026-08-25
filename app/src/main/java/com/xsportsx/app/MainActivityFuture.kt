package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivityFuture : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var connectSource by remember { mutableStateOf(false) }
            var liveFilter by remember { mutableStateOf<String?>(null) }
            var schedules by remember { mutableStateOf(false) }
            var sourceVersion by remember { mutableIntStateOf(0) }
            var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
            var updateBusy by remember { mutableStateOf(false) }
            var updateMessage by remember { mutableStateOf<String?>(null) }
            val scope = rememberCoroutineScope()
            val connected = remember(sourceVersion) { SourceStore(this@MainActivityFuture).load().isConfigured() }

            LaunchedEffect(Unit) {
                availableUpdate = AppUpdateManager.check(this@MainActivityFuture)
            }

            if (availableUpdate != null) {
                val update = availableUpdate!!
                AlertDialog(
                    onDismissRequest = { if (!updateBusy) availableUpdate = null },
                    title = { Text("XSportsX UPDATE AVAILABLE") },
                    text = { Text("Version ${update.versionName} is ready.\n\n${update.notes}") },
                    confirmButton = {
                        TextButton(enabled = !updateBusy, onClick = {
                            updateBusy = true
                            updateMessage = null
                            scope.launch {
                                val result = AppUpdateManager.downloadAndInstall(this@MainActivityFuture, update)
                                updateBusy = false
                                result.exceptionOrNull()?.let { updateMessage = it.message ?: "Update failed" }
                            }
                        }) { Text(if (updateBusy) "DOWNLOADING…" else "UPDATE NOW") }
                    },
                    dismissButton = {
                        TextButton(enabled = !updateBusy, onClick = { availableUpdate = null }) { Text("LATER") }
                    }
                )
            }

            if (updateMessage != null) {
                AlertDialog(
                    onDismissRequest = { updateMessage = null },
                    title = { Text("UPDATE") },
                    text = { Text(updateMessage!!) },
                    confirmButton = { TextButton(onClick = { updateMessage = null }) { Text("OK") } }
                )
            }

            when {
                connectSource -> SourceConnectScreen(onBack = { connectSource = false }, onSaved = { sourceVersion++; connectSource = false })
                schedules -> SportsScheduleScreen(onBack = { schedules = false }, onEvent = { event -> liveFilter = listOf(event.home, event.away, event.broadcast).filter { it.isNotBlank() }.joinToString("||"); schedules = false })
                liveFilter != null -> LiveChannelsScreen(filter = liveFilter, onBack = { liveFilter = null })
                else -> key(sourceVersion) {
                    Box(Modifier.fillMaxSize()) {
                        FuturisticHome(
                            onConnect = { if (connected) schedules = true else connectSource = true },
                            onNetwork = { network -> if (connected) liveFilter = network.name else connectSource = true }
                        )
                        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).padding(bottom = 2.dp))
                    }
                }
            }
        }
    }
}
