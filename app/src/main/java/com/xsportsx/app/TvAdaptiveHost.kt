package com.xsportsx.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density

@Composable
fun TvAdaptiveHost(onConnect: () -> Unit = {}, onNetwork: (String) -> Unit = {}) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val baseDensity = LocalDensity.current
        val widthScale = maxWidth.value / 1280f
        val heightScale = maxHeight.value / 720f
        val scale = minOf(widthScale, heightScale).coerceIn(0.85f, 1.35f)
        CompositionLocalProvider(LocalDensity provides Density(baseDensity.density * scale, baseDensity.fontScale * scale)) {
            Box(Modifier.fillMaxSize()) { TvHomeUltimate(onConnect = onConnect, onNetwork = onNetwork) }
        }
    }
}
