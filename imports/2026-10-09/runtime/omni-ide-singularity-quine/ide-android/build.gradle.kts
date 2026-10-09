plugins { id("com.android.application"); kotlin("android") }
android {
  namespace = "com.singularity.ide"
  compileSdk = 34
  defaultConfig { applicationId = "com.singularity.ide"; minSdk = 26 }
}
dependencies {
  implementation(project(":antigravity-ui"))
  implementation(project(":frontal-cortex"))
  implementation(project(":singularity-builder"))
}
