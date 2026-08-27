package com.xsportsx.app

import android.view.ViewGroup
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView

@Composable
fun NativePlayerScreen(streamUrl: String, title: String = "XSportsX", onBack: () -> Unit) {
    if (isYouTubeUrl(streamUrl)) {
        YouTubeEventPlayer(streamUrl, title, onBack)
        return
    }

    val context = androidx.compose.ui.platform.LocalContext.current
    var error by remember { mutableStateOf<String?>(null) }
    val player = remember(streamUrl) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(streamUrl))
            prepare()
            playWhenReady = true
            addListener(object : Player.Listener {
                override fun onPlayerError(exception: PlaybackException) { error = exception.message ?: "Playback error" }
            })
        }
    }
    DisposableEffect(player) { onDispose { player.release() } }
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        AndroidView(factory = {
            PlayerView(it).apply {
                this.player = player
                useController = true
                controllerAutoShow = true
                setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            }
        }, modifier = Modifier.fillMaxSize())
        Column(Modifier.align(Alignment.TopStart).padding(18.dp)) {
            TextButton(onClick = onBack) { Text("‹ BACK", color = Color.White) }
            Text(title, color = Color.White, style = MaterialTheme.typography.titleMedium)
        }
        error?.let { msg ->
            Surface(Modifier.align(Alignment.Center), color = Color(0xDD120F14)) {
                Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("STREAM ERROR", color = Color(0xFFFF536C))
                    Spacer(Modifier.height(8.dp)); Text(msg, color = Color.White)
                    Spacer(Modifier.height(12.dp)); TextButton(onClick = { error = null; player.prepare(); player.play() }) { Text("RETRY") }
                }
            }
        }
    }
}
