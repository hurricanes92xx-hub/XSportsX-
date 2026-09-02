plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.xsportsx.app"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.xsportsx.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 30
        versionName = "1.8.4"
        buildConfigField("String", "PAIRING_BASE_URL", "\"https://github.com/hurricanes92xx-hub/XSportsX-\"")
        buildConfigField("String", "SPORTS_SOURCE_URL", "\"https://xsportsx-sports-source.onrender.com\"")
    }
    flavorDimensions += "device"
    productFlavors {
        create("mobile") { dimension = "device"; applicationIdSuffix = ".mobile"; buildConfigField("boolean", "IS_TV_BUILD", "false") }
        create("tv") { dimension = "device"; applicationIdSuffix = ".tv"; buildConfigField("boolean", "IS_TV_BUILD", "true") }
    }
    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("XSORTSX_KEYSTORE_PATH")
            val storePassword = System.getenv("XSORTSX_KEYSTORE_PASSWORD")
            val keyAlias = System.getenv("XSORTSX_KEY_ALIAS")
            val keyPassword = System.getenv("XSORTSX_KEY_PASSWORD")
            if (listOf(keystorePath, storePassword, keyAlias, keyPassword).all { !it.isNullOrBlank() }) {
                storeFile = file(keystorePath!!); this.storePassword = storePassword; this.keyAlias = keyAlias; this.keyPassword = keyPassword
            }
        }
    }
    buildTypes {
        getByName("debug") { signingConfig = signingConfigs.getByName("debug") }
        getByName("release") { isMinifyEnabled = false; signingConfig = signingConfigs.getByName("release") }
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
kotlin { jvmToolchain(17) }
dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.04.01")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.2")
    implementation("androidx.browser:browser:1.9.0")
    implementation("io.coil-kt.coil3:coil-compose:3.3.0")
    implementation("io.coil-kt.coil3:coil-network-okhttp:3.3.0")
    implementation("com.google.zxing:core:3.5.3")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("androidx.camera:camera-camera2:1.6.1")
    implementation("androidx.camera:camera-lifecycle:1.6.1")
    implementation("androidx.camera:camera-view:1.6.1")
    implementation("androidx.security:security-crypto:1.1.0")
    implementation("androidx.media3:media3-exoplayer:1.11.0")
    implementation("androidx.media3:media3-exoplayer-hls:1.11.0")
    implementation("androidx.media3:media3-ui:1.11.0")
    implementation("com.caverock:androidsvg-aar:1.4")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
