# SINGULARITY OMNI IDE - Self-Hosting Skeleton

This is CodeAssist v3 evolved:
- No Gradle daemon, task DAG with fingerprint checks
- Flat-memory index (disk-backed segments + bounded cache)
- On-device toolchain: ecj + D8/R8 + aapt2 + apksigner
- Build in Service/daemon for RCE isolation

Layers:
1. antigravity-ui: JBox2D repulsion, orbital file system, zero-G canvas
2. frontal-cortex: working memory (7±2), attention, inhibition, planning
3. singularity-builder: self-hosting loop that builds its own next APK

Run:
./gradlew :ide-desktop:run  # desktop
./gradlew :ide-android:assembleDebug # self-build

Self-host test:
CI_CORE_ONLY=true ./gradlew check -> must be >2400 tests


## SINGULARITY QUINE - Self Auto-Running with Fallback

3-layer redundant self-hosting:

**Trigger:** User types command palette "Singularity: Bootstrap Self" -> Intent TRIGGER_SINGULARITY
No background auto-run - explicit user consent required per Android security.

**Layer 1 Primary:** Normal SingularityLoop -> BuildDaemon Service -> assembleDebug -> PackageInstaller (user sees install dialog)

**Layer 2 Data URL Fallback:** If project files corrupted, minimal builder is baked into APK as base64 data URL:
`data:application/vnd.singularity.builder;base64,UEsDBBQ...`
This jar contains ecj + D8 + aapt2 wrapper. Decoded at runtime, builds recovery APK without needing source files on disk.

**Layer 3 Quine:** SingularityQuineService.kt contains its own source as const QUINE_SOURCE.
Property: program prints its own source. So even if file deleted, running DEX still holds source in memory and can recreate itself.

Data URL quine in HTML: `quine_self_contained.html` is HTML whose base64 data URL is inside itself.

Build entire self-install APK:
./gradlew :ide-android:assembleDebug
APK will be at ide-android/build/outputs/apk/debug/ide-android-debug.apk
Install: adb install -r ide-android-debug.apk

Then inside app: Command Palette -> "Singularity: Bootstrap Self"
