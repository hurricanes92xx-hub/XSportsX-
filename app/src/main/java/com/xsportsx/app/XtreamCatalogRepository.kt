package com.xsportsx.app

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class XtreamCatalogRepository private constructor(context: Context) {
    private val dao = XtreamCatalogDatabase.get(context).channels()

    suspend fun replaceAll(providerKey: String, channels: List<XtreamSourceIndex.Channel>) = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        channels.chunked(500).forEach { chunk -> dao.upsertAll(chunk.map { it.toEntity(providerKey, now) }) }
        dao.deleteStale(providerKey, now - 7 * 24 * 60 * 60 * 1000L)
    }

    suspend fun replaceCategory(providerKey: String, channels: List<XtreamSourceIndex.Channel>) = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        dao.upsertAll(channels.map { it.toEntity(providerKey, now) })
    }

    suspend fun search(providerKey: String, terms: List<String>, limit: Int = 12): List<XtreamSourceIndex.Channel> = withContext(Dispatchers.IO) {
        val normalized = terms.map(::normalize).filter { it.length >= 2 }.distinct()
        if (normalized.isEmpty()) return@withContext dao.all(providerKey, limit).map { it.toChannel() }
        val rows = linkedMapOf<String, XtreamCatalogEntity>()
        normalized.forEach { term -> dao.search(providerKey, term, limit).forEach { rows[it.key] = it } }
        rows.values.take(limit).map { it.toChannel() }
    }

    suspend fun count(providerKey: String): Int = withContext(Dispatchers.IO) { dao.count(providerKey) }

    fun providerKey(config: SourceConfig): String = sha1("${config.server}|${config.username}")

    private fun XtreamSourceIndex.Channel.toEntity(providerKey: String, now: Long) = XtreamCatalogEntity(
        key = "$providerKey:$id",
        providerKey = providerKey,
        streamId = id,
        name = name,
        normalizedName = normalize(name),
        categoryId = categoryId,
        groupName = group,
        normalizedGroup = normalize(group),
        icon = icon,
        lastSeenAt = now
    )

    private fun XtreamCatalogEntity.toChannel() = XtreamSourceIndex.Channel(
        id = streamId,
        name = name,
        categoryId = categoryId,
        group = groupName,
        icon = icon
    )

    private fun normalize(value: String): String = value.lowercase()
        .replace("+", " plus ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
        .replace(Regex("\\s+"), " ")

    private fun sha1(value: String): String {
        val bytes = java.security.MessageDigest.getInstance("SHA-1").digest(value.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }

    companion object {
        @Volatile private var INSTANCE: XtreamCatalogRepository? = null

        fun get(context: Context): XtreamCatalogRepository =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: XtreamCatalogRepository(context.applicationContext).also { INSTANCE = it }
            }
    }
}
