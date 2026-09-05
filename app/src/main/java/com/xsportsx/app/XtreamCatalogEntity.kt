package com.xsportsx.app

import androidx.room3.Entity
import androidx.room3.Index
import androidx.room3.PrimaryKey

@Entity(
    tableName = "xtream_channels",
    indices = [
        Index(value = ["providerKey", "normalizedName"]),
        Index(value = ["providerKey", "normalizedGroup"]),
        Index(value = ["providerKey", "categoryId"]),
        Index(value = ["providerKey", "lastSeenAt"])
    ]
)
data class XtreamCatalogEntity(
    @PrimaryKey val key: String,
    val providerKey: String,
    val streamId: String,
    val name: String,
    val normalizedName: String,
    val categoryId: String,
    val groupName: String,
    val normalizedGroup: String,
    val icon: String,
    val lastSeenAt: Long
)
