package com.xsportsx.app

import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusState
import androidx.compose.ui.focus.onFocusChanged as composeOnFocusChanged

/** Compatibility bridge for TV focus state handling. */
fun Modifier.onFocusChanged(block: (FocusState) -> Unit): Modifier =
    this.composeOnFocusChanged(block)
