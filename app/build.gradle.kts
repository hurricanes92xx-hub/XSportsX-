plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android { namespace = "com.xsportsx.app"; compileSdk = 36
    defaultConfig { applicationId = "com.xsportsx.app"; minSdk = 26; targetSdk = 36; versionCode = 4; versionName = "1.3.0" }
}

kotlin { jvmToolchain(17) }
android { buildFeatures { compose = true } }

dependencies {
    // Keep the build on the API 36 / AGP 8.13 toolchain.
    // Compose BOM 2026.08.00 requires compileSdk 37 and AGP 9.1.2+.
    val composeBom = platform("androidx.compose:compose-bom:2026.06.01")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.9.3")
    implementation("io.coil-kt.coil3:coil-compose:3.3.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.2")
    implementation("com.google.zxing:core:3.5.3")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("androidx.camera:camera-camera2:1.5.0")
    implementation("androidx.camera:camera-lifecycle:1.5.0")
    implementation("androidx.camera:camera-view:1.5.0")
    implementation("androidx.security:security-crypto:1.1.0")
    implementation("androidx.media3:media3-exoplayer:1.9.0")
    implementation("androidx.media3:media3-ui:1.9.0")
    implementation("androidx.media3:media3-common:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
