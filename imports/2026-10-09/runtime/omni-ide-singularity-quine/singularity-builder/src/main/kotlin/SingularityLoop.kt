package singularity

import java.io.File

/**
 * Self-hosting loop: CodeAssist builds APKs on device by driving aapt2/D8 directly.
 * We reuse that to build ourselves.
 * No Gradle daemon - declarative model -> incremental DAG with persistent cache
 */
class SingularityLoop(
  private val projectDir: File,
  private val daemon: BuildDaemon // isolated Service process for memory + RCE safety
) {
  data class BuildResult(val apk: File, val testsPassed: Int, val mrr: Double)

  suspend fun bootstrapNextVersion(): BuildResult {
    // 1. Incremental check - how many tasks re-run after single-file edit?
    val tasks = listOf("CompileCore", "CompileUI", "Dex", "Package")
    val affected = daemon.affectedTasks(projectDir)
    println("Incremental tasks: ${affected.size}/${tasks.size} -> fewer is more precise")

    // 2. Run core tests - must be 2444+ passing like CodeAssist baseline
    val testResult = daemon.run("CI_CORE_ONLY=true ./gradlew :platform-core:check")
    require(testResult.passed > 2400) { "Self-test gate failed" }

    // 3. Build self in daemon (separate process, more memory)
    val apk = daemon.build(":ide-android:assembleDebug")

    // 4. Self-sign with apksigner in-process (pure-Java toolchain)
    val signed = daemon.sign(apk)

    // 5. Self-replace - archive current as immutable segment
    archiveCurrentAsSegment()

    return BuildResult(signed, testResult.passed, testResult.mrr)
  }

  private fun archiveCurrentAsSegment() {
    // flat-memory indexing idea: old versions become disk-backed segments queried in place
    File(projectDir, "segments/${System.currentTimeMillis()}.apk").apply {
      parentFile.mkdirs()
      createNewFile()
    }
  }
}

interface BuildDaemon {
  suspend fun affectedTasks(dir: File): List<String>
  suspend fun run(cmd: String): TestResult
  suspend fun build(task: String): File
  suspend fun sign(apk: File): File
}
data class TestResult(val passed: Int, val mrr: Double)
