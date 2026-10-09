plugins { kotlin("jvm") }
dependencies {
  implementation(project(":platform-core"))
  implementation(project(":index-api"))
  implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
}
