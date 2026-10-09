package antigravity

import kotlinx.coroutines.flow.MutableStateFlow
import kotlin.math.hypot

@JvmInline value class NodeId(val id: String)

data class OrbitalNode(
  val id: NodeId,
  var x: Float, var y: Float,
  var vx: Float = 0f, var vy: Float = 0f,
  var mass: Float = 1f,
  var orbitRadius: Float // distance from project core, based on recency
)

class AntigravityKernel {
  val nodes = MutableStateFlow<List<OrbitalNode>>(emptyList())
  private val G = 0.08f // antigravity repulsion constant

  // Frontal Cortex working memory keeps 7±2 hot nodes closest
  fun update(dt: Float) {
    val list = nodes.value
    for (i in list.indices) {
      for (j in i+1 until list.size) {
        val a = list[i]; val b = list[j]
        val dx = a.x - b.x; val dy = a.y - b.y
        val dist = hypot(dx, dy).coerceAtLeast(60f) // no overlap
        val force = G * a.mass * b.mass / (dist*dist)
        val fx = dx / dist * force; val fy = dy / dist * force
        a.vx += fx; a.vy += fy
        b.vx -= fx; b.vy -= fy
      }
      // orbital pull to center (project core)
      list[i].vx += -list[i].x * 0.001f
      list[i].vy += -list[i].y * 0.001f
      list[i].x += list[i].vx * dt
      list[i].y += list[i].vy * dt
      list[i].vx *= 0.98f; list[i].vy *= 0.98f // damping = zero-G drag
    }
    nodes.value = list
  }

  fun bringToFront(id: NodeId) {
    // working memory promotion - shrink orbit
    nodes.value.find { it.id == id }?.let { it.orbitRadius *= 0.7f }
  }
}
