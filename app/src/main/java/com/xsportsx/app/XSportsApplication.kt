package com.xsportsx.app

import android.app.Application

/**
 * Process-level bootstrap for the single schedule/live runtime engine.
 *
 * Mobile and TV screens consume ScheduleEngine.state; they do not own their
 * own schedule polling loops. This keeps warm schedule and hot live state
 * coherent across the entire application process.
 */
class XSportsApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        ScheduleEngine.start()
    }
}
