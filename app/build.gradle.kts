plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android { namespace = "com.xsportsx.app"; compileSdk = 36
    defaultConfig { applicationId = "com.xsportsx.app"; minSdk = 26; targetSdk = 36; versionCode = 1; versionName = "1.0.0" }
}

kotlin { jvmToolchain(17) }

android { buildFeatures { compose = true } }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.08.00")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.9.3")
    implementation("io.coil-kt.coil3:coil-compose:3.3.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
