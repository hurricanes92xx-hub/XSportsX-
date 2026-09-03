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
        // Supplying context here enables background event prewarming before any
        // sports screen is opened. The launcher loading activity also calls start
        // defensively, but ScheduleEngine is idempotent.
        ScheduleEngine.start(this)
    }
}
