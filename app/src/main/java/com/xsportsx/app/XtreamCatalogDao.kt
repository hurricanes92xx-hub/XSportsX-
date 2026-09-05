package com.xsportsx.app

import androidx.room3.Dao
import androidx.room3.Insert
import androidx.room3.OnConflictStrategy
import androidx.room3.Query

@Dao
interface XtreamCatalogDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<XtreamCatalogEntity>)

    @Query("SELECT * FROM xtream_channels WHERE providerKey = :providerKey ORDER BY normalizedName LIMIT :limit")
    suspend fun all(providerKey: String, limit: Int): List<XtreamCatalogEntity>

    @Query("SELECT * FROM xtream_channels WHERE providerKey = :providerKey AND (normalizedName LIKE '%' || :term || '%' OR normalizedGroup LIKE '%' || :term || '%') ORDER BY normalizedName LIMIT :limit")
    suspend fun search(providerKey: String, term: String, limit: Int): List<XtreamCatalogEntity>

    @Query("SELECT * FROM xtream_channels WHERE providerKey = :providerKey AND categoryId IN (:categoryIds) ORDER BY normalizedName LIMIT :limit")
    suspend fun byCategories(providerKey: String, categoryIds: List<String>, limit: Int): List<XtreamCatalogEntity>

    @Query("DELETE FROM xtream_channels WHERE providerKey = :providerKey AND lastSeenAt < :cutoff")
    suspend fun deleteStale(providerKey: String, cutoff: Long): Int

    @Query("SELECT COUNT(*) FROM xtream_channels WHERE providerKey = :providerKey")
    suspend fun count(providerKey: String): Int
}
