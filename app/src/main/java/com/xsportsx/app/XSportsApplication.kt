package com.xsportsx.app

import android.app.Application

/**
 * Process-level bootstrap for the single schedule/live runtime engine and the
 * user's authorized Xtream/M3U source synchronization.
 */
class XSportsApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Schedule data and user-source synchronization both start immediately,
        // but neither blocks the first UI frame.
        ScheduleEngine.start(this)
        UserSourceSyncEngine.schedule(this)
    }
}
