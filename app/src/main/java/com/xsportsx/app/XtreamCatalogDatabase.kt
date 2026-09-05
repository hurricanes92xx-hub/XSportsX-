package com.xsportsx.app

import android.content.Context
import androidx.room3.Database
import androidx.room3.Room
import androidx.room3.RoomDatabase
import androidx.sqlite.driver.AndroidSQLiteDriver
import kotlinx.coroutines.Dispatchers

@Database(entities = [XtreamCatalogEntity::class], version = 1, exportSchema = false)
abstract class XtreamCatalogDatabase : RoomDatabase() {
    abstract fun channels(): XtreamCatalogDao

    companion object {
        @Volatile private var INSTANCE: XtreamCatalogDatabase? = null

        fun get(context: Context): XtreamCatalogDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder<XtreamCatalogDatabase>(
                    context.applicationContext,
                    "xsportsx_xtream_catalog.db"
                )
                    .setDriver(AndroidSQLiteDriver())
                    .setQueryCoroutineContext(Dispatchers.IO)
                    .build()
                    .also { INSTANCE = it }
            }
    }
}
