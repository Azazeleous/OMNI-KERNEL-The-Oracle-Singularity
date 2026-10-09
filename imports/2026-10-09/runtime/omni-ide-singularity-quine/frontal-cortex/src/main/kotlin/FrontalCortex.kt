package cortex

import kotlinx.coroutines.flow.MutableStateFlow

// Mimics human executive functions - CodeAssist's flat-memory index is our long-term memory
class FrontalCortex(
  private val index: FlatMemoryIndex // disk-backed immutable segments
) {
  // Working Memory: 7±2 items, bounded block cache
  val workingMemory = MutableStateFlow<List<Symbol>>(emptyList())

  enum class ExecutiveSignal { ATTEND, INHIBIT, PLAN }

  // Attentional spotlight - pre-warms compilation env like CodeAssist does per keystroke
  suspend fun attend(file: String, cursorOffset: Int): ExecutiveSignal {
    val symbols = index.queryPrefix(file.substring(0, 3), limit = 7)
    workingMemory.value = symbols
    return if (index.willBuildFail(file)) ExecutiveSignal.INHIBIT else ExecutiveSignal.ATTEND
  }

  // Planning - decomposes intent into Task DAG (Gradle's good ideas, none of its weight)
  fun plan(intent: String): List<BuildTask> {
    // e.g. "make login screen" -> [ResourceTask, JavaCompile, Dex, Package]
    return when {
      intent.contains("login") -> listOf(
        BuildTask("ResourceTask", inputs = listOf("layout/login.xml")),
        BuildTask("CompileTask", inputs = listOf("Login.kt")),
        BuildTask("PackageTask")
      )
      else -> listOf(BuildTask("IncrementalCompile"))
    }
  }

  // Inhibitory control - fingerprint up-to-date check
  fun shouldInhibit(task: BuildTask): Boolean {
    return task.fingerprint == task.lastFingerprint // up-to-date
  }
}

data class BuildTask(val name: String, val inputs: List<String> = emptyList(), val fingerprint: String = "", val lastFingerprint: String = "")
interface FlatMemoryIndex {
  fun queryPrefix(p: String, limit: Int): List<Symbol>
  fun willBuildFail(file: String): Boolean
}
data class Symbol(val name: String)
