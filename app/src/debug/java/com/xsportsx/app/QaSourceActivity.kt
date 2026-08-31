package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent

/** Dedicated debug-only entry point for deterministic source QA. */
class QaSourceActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SourceConnectScreen(
                onBack = { finish() },
                onSaved = { finish() }
            )
        }
    }
}
