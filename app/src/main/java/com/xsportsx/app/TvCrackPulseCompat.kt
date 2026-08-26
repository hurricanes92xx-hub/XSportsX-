package com.xsportsx.app

import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember

enum class RepeatMode { Reverse }

data class TvTweenSpec(val durationMillis: Int)
data class TvRepeatSpec(val tween: TvTweenSpec, val mode: RepeatMode)

fun tween(durationMillis: Int): TvTweenSpec = TvTweenSpec(durationMillis)
fun infiniteRepeatable(tween: TvTweenSpec, repeatMode: RepeatMode): TvRepeatSpec = TvRepeatSpec(tween, repeatMode)

class TvCrackPulse {
    @Composable
    fun animateFloat(initial: Float, target: Float, spec: TvRepeatSpec, label: String): State<Float> {
        return remember { mutableFloatStateOf((initial + target) / 2f) }
    }
}

@Composable
fun rememberInfiniteTransition(label: String): TvCrackPulse = remember { TvCrackPulse() }
