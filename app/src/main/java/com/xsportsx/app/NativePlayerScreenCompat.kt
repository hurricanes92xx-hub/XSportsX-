package com.xsportsx.app

import androidx.compose.runtime.Composable

/**
 * Compatibility overload for the existing Play/Watch call sites.
 * The player now exposes playback telemetry callbacks, but older callers
 * only provide the back action. Keep that call shape source-compatible while
 * routing it to the full player implementation.
 */
@Composable
fun NativePlayerScreen(
    streamUrl: String,
    title: String,
    onBack: () -> Unit
) {
    NativePlayerScreen(
        streamUrl = streamUrl,
        title = title,
        onBack = onBack
    )
}
