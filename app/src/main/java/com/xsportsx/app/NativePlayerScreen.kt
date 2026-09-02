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
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView

@Composable
fun NativePlayerScreen(streamUrl: String, title: String = "XSportsX", onBack: () -> Unit) {
    if (isYouTubeUrl(streamUrl)) {
        YouTubeEventPlayer(streamUrl, title, onBack)
        return
    }

    val context = androidx.compose.ui.platform.LocalContext.current
    var error by remember(streamUrl) { mutableStateOf<String?>(null) }
    var activeUrl by remember(streamUrl) { mutableStateOf(streamUrl) }
    var fallbackUsed by remember(streamUrl) { mutableStateOf(false) }

    val player = remember(streamUrl) {
        val httpFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36")
            .setAllowCrossProtocolRedirects(true)
            .setConnectTimeoutMs(10_000)
            .setReadTimeoutMs(20_000)
        ExoPlayer.Builder(context)
            .setMediaSourceFactory(DefaultMediaSourceFactory(httpFactory))
            .build()
    }

    fun prepareUrl(url: String) {
        val lower = url.lowercase()
        val mime = when {
            lower.contains(".m3u8") -> MimeTypes.APPLICATION_M3U8
            lower.contains(".ts") -> MimeTypes.VIDEO_MP2T
            else -> null
        }
        val item = MediaItem.Builder().setUri(url).apply {
            if (mime != null) setMimeType(mime)
        }.build()
        player.setMediaItem(item)
        player.prepare()
        player.playWhenReady = true
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlayerError(exception: PlaybackException) {
                val lower = activeUrl.lowercase()
                val alternate = when {
                    !fallbackUsed && lower.contains(".m3u8") -> activeUrl.replace(Regex("\\.m3u8(?:\\?.*)?$", RegexOption.IGNORE_CASE), ".ts")
                    !fallbackUsed && lower.contains(".ts") -> activeUrl.replace(Regex("\\.ts(?:\\?.*)?$", RegexOption.IGNORE_CASE), ".m3u8")
                    else -> null
                }
                if (alternate != null && alternate != activeUrl) {
                    fallbackUsed = true
                    activeUrl = alternate
                    error = null
                    prepareUrl(alternate)
                } else {
                    error = exception.message ?: exception.errorCodeName
                }
            }
        }
        player.addListener(listener)
        prepareUrl(activeUrl)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }

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
                    Spacer(Modifier.height(12.dp)); TextButton(onClick = {
                        error = null
                        fallbackUsed = false
                        activeUrl = streamUrl
                        prepareUrl(streamUrl)
                    }) { Text("RETRY") }
                }
            }
        }
    }
}
