package com.xsportsx.app

import androidx.compose.ui.geometry.Offset as GeometryOffset

/**
 * Compose 1.8+ stores Offset as a packed Long. Keep the futuristic UI's
 * Offset(x, y) call sites source-compatible with the top-level factory.
 */
fun Offset(x: Float, y: Float): GeometryOffset = GeometryOffset(x, y)
