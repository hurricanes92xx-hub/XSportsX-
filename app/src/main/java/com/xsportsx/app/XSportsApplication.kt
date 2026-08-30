package com.xsportsx.app

import android.app.Application
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Keeps schedule reconciliation off the UI thread. The visible screens still
 * request only their three-day window; this worker quietly refreshes a broader
 * window while the app process is alive.
 */
class XSportsApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        ScheduleBackgroundSync.start()
    }
}

object ScheduleBackgroundSync {
    @Volatile var latest: List<SportsEvent> = emptyList()
        private set
    @Volatile var lastUpdatedMillis: Long = 0L
        private set

    private const val REFRESH_MS = 5L * 60L * 1000L
    private var started = false

    fun start() {
        if (started) return
        started = true
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            while (isActive) {
                runCatching {
                    latest = SportsScheduleService.loadBackground()
                    lastUpdatedMillis = System.currentTimeMillis()
                }
                delay(REFRESH_MS)
            }
        }
    }
}
