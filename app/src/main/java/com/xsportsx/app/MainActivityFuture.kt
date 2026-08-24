package com.xsportsx.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*

class MainActivityFuture : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var connectSource by remember { mutableStateOf(false) }
            if (connectSource) {
                SourceConnectScreen(
                    onBack = { connectSource = false },
                    onSaved = { connectSource = false }
                )
            } else {
                FuturisticHome(
                    onConnect = { connectSource = true },
                    onNetwork = { connectSource = true }
                )
            }
        }
    }
}
