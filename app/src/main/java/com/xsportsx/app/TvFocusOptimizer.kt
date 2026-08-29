package com.xsportsx.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.indication
import androidx.compose.foundation.LocalIndication
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.key.onKeyEvent

/**
 * Android TV-safe click target.
 *
 * The old plain clickable path could show focus but lose the first DPAD_CENTER/ENTER
 * activation while focus/AnimatedContent was settling. This modifier makes the target
 * explicitly focusable and consumes the key-up activation exactly once.
 */
@Composable
fun Modifier.tvClickable(onClick: () -> Unit): Modifier {
    val interactionSource = remember { MutableInteractionSource() }
    return this
        .focusable()
        .onKeyEvent { event ->
            if (event.type == KeyEventType.KeyUp &&
                (event.key == Key.DirectionCenter || event.key == Key.Enter || event.key == Key.NumPadEnter)
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
