package com.xsportsx.app

import android.content.Context

/** Stores channel identities, not credential-bearing stream URLs. */
object ChannelFavorites {
    private const val PREFS = "xsportsx_channel_favorites"
    private const val KEY = "channels"

    private fun id(stream: ResolvedStream): String = "${stream.name.trim()}\u001f${stream.group.trim()}"

    fun load(context: Context): Set<String> = context.applicationContext
        .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        .getStringSet(KEY, emptySet())
        .orEmpty()

    fun isFavorite(context: Context, stream: ResolvedStream): Boolean = id(stream) in load(context)

    fun toggle(context: Context, stream: ResolvedStream): Boolean {
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val current = prefs.getStringSet(KEY, emptySet()).orEmpty().toMutableSet()
        val key = id(stream)
        val added = current.add(key)
        if (!added) current.remove(key)
        prefs.edit().putStringSet(KEY, current).apply()
        return added
    }
}
