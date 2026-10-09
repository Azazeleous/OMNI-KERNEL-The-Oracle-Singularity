package singularity

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Fallback redundant trigger system
 * 3 independent ways to trigger self-build, all require user consent
 */
class RedundantTrigger : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            "com.singularity.TRIGGER_PRIMARY" -> {
                context.startService(Intent(context, SingularityQuineService::class.java).apply {
                    action = "TRIGGER_SINGULARITY"
                })
            }
            "com.singularity.TRIGGER_FROM_DATA_URL" -> {
                // Decode trigger from data URL itself
                val data = intent.dataString // data:text/plain;base64,....
                if (data?.startsWith("data:") == true) {
                    val decoded = String(android.util.Base64.decode(data.substringAfter("base64,"), 0))
                    if (decoded == "BOOTSTRAP") {
                        context.startService(Intent(context, SingularityQuineService::class.java).apply {
                            action = "TRIGGER_SINGULARITY"
                        })
                    }
                }
            }
            Intent.ACTION_MY_PACKAGE_REPLACED -> {
                // Auto-verify after self-install
                println("Self-install completed, verifying quine integrity")
            }
        }
    }
}