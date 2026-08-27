package com.xsportsx.app

import android.annotation.SuppressLint
import android.graphics.Color as AndroidColor
import android.view.ViewGroup
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

private fun youtubeId(value: String): String? {
    val v = value.trim()
    if (v.matches(Regex("[A-Za-z0-9_-]{11}"))) return v
    return Regex("(?:v=|youtu\\.be/|youtube\\.com/(?:embed/|shorts/))([A-Za-z0-9_-]{11})").find(v)?.groupValues?.getOrNull(1)
}

fun isYouTubeUrl(value: String): Boolean = youtubeId(value) != null

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun YouTubeEventPlayer(videoIdOrUrl: String, title: String = "XSportsX", onBack: () -> Unit) {
    val id = youtubeId(videoIdOrUrl)
    var error by remember(videoIdOrUrl) { mutableStateOf(id == null) }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (id != null) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { context ->
                    WebView(context).apply {
                        setBackgroundColor(AndroidColor.BLACK)
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.mediaPlaybackRequiresUserGesture = false
                        settings.cacheMode = WebSettings.LOAD_DEFAULT
                        webViewClient = WebViewClient()
                        webChromeClient = WebChromeClient()
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                        val html = """
                            <!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no'></head>
                            <body style='margin:0;background:#000;overflow:hidden'>
                            <iframe width='100%' height='100%' style='position:absolute;inset:0;border:0'
                              src='https://www.youtube.com/embed/$id?autoplay=1&playsinline=1&rel=0&modestbranding=1&enablejsapi=1'
                              title='${title.replace("'", "")} ' allow='autoplay; encrypted-media; picture-in-picture; fullscreen' allowfullscreen></iframe>
                            </body></html>
                        """.trimIndent()
                        loadDataWithBaseURL("https://www.youtube.com", html, "text/html", "UTF-8", null)
                    }
                },
                update = { it.loadUrl("javascript:void(0)") }
            )
            DisposableEffect(Unit) {
                onDispose {
                    // WebView is owned by AndroidView; its lifecycle is released with the composition.
                }
            }
        }
        TextButton(onClick = onBack, modifier = Modifier.align(Alignment.TopStart).padding(18.dp)) {
            Text("‹ BACK", color = Color.White)
        }
        Text(title, modifier = Modifier.align(Alignment.TopCenter).padding(22.dp), color = Color.White, style = MaterialTheme.typography.titleMedium)
        if (error) Text("YOUTUBE EVENT UNAVAILABLE", modifier = Modifier.align(Alignment.Center), color = Color(0xFFFF536C))
    }
}
