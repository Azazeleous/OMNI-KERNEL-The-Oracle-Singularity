plugins { kotlin("jvm"); id("org.jetbrains.compose") }
dependencies {
  implementation(project(":platform-core"))
  implementation(compose.runtime)
  implementation("org.jbox2d:jbox2d-library:2.2.1.1") // physics for repulsion
}
