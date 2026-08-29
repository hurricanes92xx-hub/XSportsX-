package com.xsportsx.app

import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.indication
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type

/**
 * Android TV-safe click target.
 *
 * TV gets explicit focus plus one-shot DPAD_CENTER/ENTER activation. Mobile keeps the
 * normal Compose clickable path so this optimization cannot change touch behavior.
 */
@Composable
fun Modifier.tvClickable(onClick: () -> Unit): Modifier {
    if (!BuildConfig.IS_TV_BUILD) return this.clickable(onClick = onClick)

    val interactionSource = remember { MutableInteractionSource() }
    return this
        .focusable()
        .onKeyEvent { event ->
            if (event.type == KeyEventType.KeyUp &&
                (event.key == Key.DirectionCenter || event.key == Key.Enter)
            ) {
                onClick()
                true
            } else {
                false
            }
        }
        .indication(interactionSource, LocalIndication.current)
        .clickable(
            interactionSource = interactionSource,
            indication = null,
            onClick = onClick
        )
}
