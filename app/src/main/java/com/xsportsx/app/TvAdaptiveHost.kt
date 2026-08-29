package com.xsportsx.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density

/**
 * Keeps the TV UI proportional across different Android TV panel resolutions/densities.
 * The TV home now uses the canonical SportsScheduleService feed so the home screen,
 * schedule screen and ticker do not maintain competing ESPN loaders.
 */
@Composable
fun TvAdaptiveHost(
    onConnect: () -> Unit = {},
    onNetwork: (String) -> Unit = {}
) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val baseDensity = LocalDensity.current
        val widthScale = maxWidth.value / 1280f
        val heightScale = maxHeight.value / 720f
        val scale = minOf(widthScale, heightScale).coerceIn(0.85f, 1.35f)
        CompositionLocalProvider(
            LocalDensity provides Density(
                density = baseDensity.density * scale,
                fontScale = baseDensity.fontScale * scale
            )
        ) {
            Box(Modifier.fillMaxSize()) {
                TvHomeFixed(onConnect = onConnect, onNetwork = onNetwork)
            }
        }
    }
}
