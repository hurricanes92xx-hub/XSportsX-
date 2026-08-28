package com.xsportsx.app

import android.content.pm.ActivityInfo
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class MainActivityFuture : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BuildConfig.IS_TV_BUILD) requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        setContent {
            var connectSource by remember { mutableStateOf(false) }
            var tvConnectChooser by remember { mutableStateOf(false) }
            var mobilePair by remember { mutableStateOf(false) }
            var tvPair by remember { mutableStateOf(false) }
            var liveFilter by remember { mutableStateOf<String?>(null) }
            var selectedScheduleLeague by remember { mutableStateOf<String?>(null) }
            var selectedEvent by remember { mutableStateOf<SportsEvent?>(null) }
            var schedules by remember { mutableStateOf(false) }
            var sourceVersion by remember { mutableIntStateOf(0) }
            var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
            var updateBusy by remember { mutableStateOf(false) }
            var updateProgress by remember { mutableIntStateOf(0) }
            var updateMessage by remember { mutableStateOf<String?>(null) }
            val scope = rememberCoroutineScope()
            val connected = remember(sourceVersion) { SourceStore(this@MainActivityFuture).load().isConfigured() }

            fun checkForUpdate() { scope.launch { val found = AppUpdateManager.check(this@MainActivityFuture); if (found != null && found.versionCode > (availableUpdate?.versionCode ?: 0)) availableUpdate = found } }

            LaunchedEffect(Unit) {
                checkForUpdate()
                while (isActive) { delay(30 * 60 * 1000L); checkForUpdate() }
            }
            LaunchedEffect(Unit) { scope.launch { runCatching { StreamResolver(this@MainActivityFuture).preloadLiveStreams(force = true) } } }
            LaunchedEffect(sourceVersion, connected) { if (sourceVersion > 0) runCatching { StreamResolver(this@MainActivityFuture).preloadLiveStreams(force = true) } }

            if (availableUpdate != null) {
                val update = availableUpdate!!
                AlertDialog(onDismissRequest = { if (!updateBusy) availableUpdate = null }, title = { Text("XSPORTSX UPDATE AVAILABLE") }, text = { Text(if (updateBusy) "Downloading update… $updateProgress%\n\nKeep XSportsX open until the download finishes." else "Version ${update.versionName} is ready.\n\n${update.notes}") }, confirmButton = {
                    TextButton(enabled = !updateBusy, onClick = { updateBusy = true; updateProgress = 0; updateMessage = null; scope.launch { val result = AppUpdateManager.downloadAndInstall(this@MainActivityFuture, update) { p -> updateProgress = p }; updateBusy = false; result.exceptionOrNull()?.let { updateMessage = it.message ?: "Update failed" } } }) { Text(if (updateBusy) "DOWNLOADING $updateProgress%" else "UPDATE NOW") }
                }, dismissButton = { TextButton(enabled = !updateBusy, onClick = { availableUpdate = null }) { Text("LATER") }
                })
            }
            updateMessage?.let { AlertDialog(onDismissRequest = { updateMessage = null }, title = { Text("UPDATE") }, text = { Text(it) }, confirmButton = { TextButton(onClick = { updateMessage = null }) { Text("OK") } }) }
            when {
                tvConnectChooser -> TvSourceChooser(onQr = { tvConnectChooser = false; tvPair = true }, onManual = { tvConnectChooser = false; connectSource = true }, onBack = { tvConnectChooser = false })
                tvPair -> QrPairingScreen(
                    pairingUrl = BuildConfig.PAIRING_BASE_URL,
                    onDone = {
                        // QR cancellation is an explicit navigation state transition.
                        // Clear every competing screen before restoring the chooser so the
                        // TV regression test and real remotes cannot land on the home screen.
                        tvPair = false
                        connectSource = false
                        mobilePair = false
                        schedules = false
                        selectedEvent = null
                        liveFilter = null
                        tvConnectChooser = true
                        sourceVersion++
                    },
                    onConnected = { sourceVersion++; tvPair = false; tvConnectChooser = false }
                )
                mobilePair -> PhonePairScanner(pairingBaseUrl = BuildConfig.PAIRING_BASE_URL, onConnected = { mobilePair = false }, onCancel = { mobilePair = false })
                connectSource -> SourceConnectScreen(onBack = { connectSource = false }, onSaved = { sourceVersion++; connectSource = false })
                schedules -> SportsScheduleScreen(initialLeague = selectedScheduleLeague, onBack = { schedules = false }, onEvent = { event -> selectedEvent = event; liveFilter = null; schedules = false })
                selectedEvent != null -> LiveChannelsScreen(event = selectedEvent, onBack = { selectedEvent = null })
                liveFilter != null -> LiveChannelsScreen(filter = liveFilter, onBack = { liveFilter = null })
                else -> key(sourceVersion) {
                    if (BuildConfig.IS_TV_BUILD) TvAdaptiveHost(
                        onConnect = { tvConnectChooser = true },
                        onNetwork = { network ->
                            if (network.startsWith("LEAGUE:")) {
                                selectedScheduleLeague = network.removePrefix("LEAGUE:")
                                schedules = true
                            } else {
                                selectedEvent = null
                                liveFilter = network
                            }
                        }
                    ) else Box(Modifier.fillMaxSize().background(Color(0xFF05060A))) {
                        FuturisticHome(
                            onConnect = { schedules = true },
                            onNetwork = { network ->
                                if (network.type == "LEAGUE") {
                                    selectedScheduleLeague = network.name
                                    schedules = true
                                } else {
                                    selectedEvent = null
                                    liveFilter = network.name
                                }
                            }
                        )
                        TvPairButton(connected = connected, onClick = { if (connected) mobilePair = true else connectSource = true }, modifier = Modifier.align(Alignment.TopEnd).padding(top = 20.dp, end = 24.dp))
                        HomeSportsTicker(Modifier.align(Alignment.BottomCenter).padding(bottom = 2.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun TvPairButton(connected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    OutlinedButton(onClick = onClick, modifier = modifier.height(40.dp), colors = ButtonDefaults.outlinedButtonColors(containerColor = Color(0xCC0B111A), contentColor = Color.White), border = BorderStroke(1.dp, Color(0xFFFF1838).copy(alpha = if (connected) 0.9f else 0.45f)), shape = RoundedCornerShape(14.dp)) { Text(if (connected) "⌁  CONNECT TV" else "⌁  ADD SOURCE", fontSize = 10.sp, fontWeight = FontWeight.Black) }
}