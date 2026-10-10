# Termux audio package recovery v5.0.3

The v5.0.2 audio install depends on Python, Termux:API, FFmpeg and PulseAudio. A dpkg failure must be resolved before starting the speaker check. The final dpkg error code does not identify the failing package or operation; this release captures the actual error instead of assigning a cause from an absent terminal trace.

`tools/GAIA_TERMUX_AUDIO_RECOVERY_v5.0.3.sh` is one self-contained Bash block. It contains the complete, byte-identical v5.0.2 audio installer and its Python source. No prior file in Android Downloads is needed. The recovery wrapper has version 5.0.3; the unchanged Fourier component retains version 5.0.2.

Run the downloaded monolith in the native Termux shell, or paste its entire content into that shell. A calculator URL, Markdown escapes and HTML entities are not shell commands.

The wrapper rejects other environments before package operations. It saves itself under `${AE:-$HOME/Æ}/autonomous`, creates `bin/gaia-termux-audio-repair`, and copies itself to an available Downloads directory. The saved source includes all embedded audio code. A private session folder retains the complete package-manager output, one log per step, a snapshot of the dpkg database and apt configuration, and a pre-repair status-file hash. These are diagnostic snapshots, not a complete backup or an automatic package rollback.

Its single-pass procedure is:

1. Inspect package state with `dpkg --audit`.
2. Resume unpacked but unconfigured packages with `dpkg --force-confold --configure -a`, preserving locally changed configuration files.
3. Refresh indexes from existing authenticated repositories, with one fetch retry and network/lock timeouts.
4. Attempt `apt-get --fix-broken --no-remove -y install`; stop if dependency repair requires package removal.
5. Reconfigure, check dependencies, install the four audio prerequisites, and check dependencies again.
6. Require an empty dpkg audit, all four package statuses to be `install ok installed`, and all required executables to be available.
7. Validate the embedded installer SHA-256, install it, and append a separate package-recovery receipt.
8. Start the PulseAudio server if necessary, then run the physical-microphone Fourier check.

The dependency repair and package installation may update the requested packages and needed dependencies. They do not run a distribution upgrade. The script does not remove dpkg lock files, kill another package operation, purge packages, delete the database, bypass signature verification or overwrite repository configuration. Package maintainer scripts still execute as part of real dpkg/apt recovery.

The number of repair attempts is bounded. Package maintainer scripts can take time; the wrapper does not apply a hard kill deadline to them. Network operations use 20-second timeouts and one retry; apt waits up to 15 seconds for its lock. An already-running dpkg operation causes a normal lock error and blocks the repair.

If a package step fails, audio does not start. The wrapper prints the log location and final 30 lines. Known lock failures suggest waiting for the existing operation. Repository-fetch failures suggest restoring connectivity or selecting a working mirror using `termux-change-repo`, then rerunning the saved repair. It cannot select the correct remedy for an unknown failure without that actual error.

The package receipt reports dependency/audit/package/executable evidence and always leaves `acoustic_playback_verified` false. Only the later microphone challenge can return a conditional acoustic result. A package-success receipt is not sound playback proof.

Termux:API's Android app must also be installed from a source compatible with the main Termux app and have microphone access. Installing the `termux-api` CLI package cannot install that Android app. Keep the microphone physically exposed to the intended speaker while the check runs.

This workspace has verified Bash parsing, actual Bash function serialization with complete embedded-source retention, the original installer's byte identity and SHA-256, and actual rejection of the non-Termux host. It has not performed package repair on the user's phone or acoustic playback. The prior v5.0.2 component's 50-test software report remains applicable to its unchanged bytes. See [v5.0.3 verification](termux_audio_recovery_verification_v5.0.3.json) and [v5.0.2 microphone workflow](audio_feedback_v5.0.2.md).

Primary command references: [dpkg configure/audit/conffile behavior](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html), [apt-get dependency repair and no-removal behavior](https://manpages.debian.org/trixie/apt/apt-get.8.en.html), [Termux repository troubleshooting](https://github.com/termux/termux-packages/wiki/Package-Management), [Termux:API installation](https://github.com/termux/termux-api#installation). The Termux wiki page contains historical distribution guidance; use its repository troubleshooting instructions without assuming that its old app-version or Play Store statements describe current builds.
