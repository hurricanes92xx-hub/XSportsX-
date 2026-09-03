package com.xsportsx.app

import android.content.Intent
import android.content.pm.ActivityInfo
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.*

class StartupLoadingActivity : ComponentActivity() {
    private val workScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BuildConfig.IS_TV_BUILD) requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE

        // Give ScheduleEngine the application context before its first publish so
        // the normal background prewarm coordinator is active from app launch.
        ScheduleEngine.start(this)

        setContent {
            StartupLoadingScreen(onFinished = {
                startActivity(Intent(this@StartupLoadingActivity, MainActivityFuture::class.java).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
                })
                finish()
            })
        }
    }

    override fun onDestroy() {
        workScope.cancel()
        super.onDestroy()
    }
}

@Composable
private fun StartupLoadingScreen(onFinished: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val state by ScheduleEngine.state.collectAsState()
    var channelsReady by remember { mutableStateOf(false) }
    var minimumTimeDone by remember { mutableStateOf(false) }
    var timedOut by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        coroutineScope {
            launch {
                runCatching {
                    StreamResolver(context).preloadLiveStreams(force = true)
                }
                channelsReady = true
            }
            launch {
                delay(1400L)
                minimumTimeDone = true
            }
            launch {
                delay(5200L)
                timedOut = true
            }
        }
    }

    LaunchedEffect(state.events, channelsReady, minimumTimeDone, timedOut) {
        if (minimumTimeDone && (state.events.isNotEmpty() && channelsReady || timedOut)) {
            delay(180L)
            onFinished()
        }
    }

    val transition = rememberInfiniteTransition(label = "startup-pulse")
    val pulse by transition.animateFloat(
        initialValue = 0.72f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(750, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "startup-pulse-alpha"
    )
    val stage = when {
        state.events.isEmpty() -> "LOADING LIVE SCHEDULES"
        !channelsReady -> "SYNCING CHANNELS & SOURCES"
        else -> "RESOLVING BEST STREAMS"
    }
    val progress = when {
        state.events.isEmpty() -> 24
        !channelsReady -> 58
        else -> 92
    }

    Box(
        Modifier.fillMaxSize().background(
            Brush.verticalGradient(listOf(Color(0xFF030509), Color(0xFF0A0D14), Color(0xFF030509)))
        ).padding(horizontal = 28.dp, vertical = 22.dp)
    ) {
        Column(
            Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            XtremeLogo(Modifier.alpha(pulse), size = if (BuildConfig.IS_TV_BUILD) 156.dp else 132.dp)
            Spacer(Modifier.height(18.dp))
            Text("XSPORTSX", color = Color.White, fontSize = if (BuildConfig.IS_TV_BUILD) 34.sp else 30.sp, fontWeight = FontWeight.Black, letterSpacing = 5.sp)
            Text("LIVE GAMES. EVERY SPORT. ONE PLACE.", color = Color(0xFF8D94A2), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            Spacer(Modifier.height(34.dp))
            Text("PREPARING YOUR ULTIMATE SPORTS EXPERIENCE", color = Color(0xFFFF1838), fontSize = 13.sp, fontWeight = FontWeight.Black, letterSpacing = 1.5.sp)
            Spacer(Modifier.height(18.dp))
            StartupStep("✓", "Loading Live Schedules", state.events.isNotEmpty())
            StartupStep(if (channelsReady) "✓" else "•", "Syncing Channels & Sources", channelsReady)
            StartupStep(if (channelsReady) "◉" else "•", "Resolving Best Streams", channelsReady)
            StartupStep("•", "Checking Stream Health", false)
            StartupStep("•", "Optimizing For Speed", false)
            Spacer(Modifier.height(22.dp))
            Text("OVERALL PROGRESS", color = Color(0xFF707887), fontSize = 9.sp, fontWeight = FontWeight.Black, letterSpacing = 3.sp)
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(if (BuildConfig.IS_TV_BUILD) .62f else .92f), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f).height(10.dp).clip(RoundedCornerShape(8.dp)).background(Color(0xFF171B24))) {
                    Box(Modifier.fillMaxWidth(progress / 100f).fillMaxHeight().clip(RoundedCornerShape(8.dp)).background(Brush.horizontalGradient(listOf(Color(0xFFFF102F), Color(0xFFFF5268)))))
                }
                Spacer(Modifier.width(10.dp))
                Text("$progress%", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Black)
            }
            Spacer(Modifier.height(18.dp))
            Box(Modifier.fillMaxWidth(if (BuildConfig.IS_TV_BUILD) .62f else .92f).clip(RoundedCornerShape(18.dp)).background(Color(0xCC0D1119)).padding(16.dp)) {
                Column {
                    Text(stage, color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Black)
                    Spacer(Modifier.height(5.dp))
                    Text("Using cached schedules and preparing the fastest known stream candidates.", color = Color(0xFF777F8C), fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
private fun StartupStep(marker: String, label: String, complete: Boolean) {
    Row(Modifier.fillMaxWidth(if (BuildConfig.IS_TV_BUILD) .62f else .92f).padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(marker, color = if (complete) Color(0xFFFF1838) else Color(0xFF4D5562), fontSize = 15.sp, fontWeight = FontWeight.Black)
        Spacer(Modifier.width(12.dp))
        Text(label, color = if (complete) Color.White else Color(0xFF858C99), fontSize = 12.sp, fontWeight = if (complete) FontWeight.Bold else FontWeight.Normal)
    }
}
