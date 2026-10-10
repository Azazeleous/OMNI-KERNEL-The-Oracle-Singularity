# GAIA audio mixture v5.0.4

The diagnostic collects the existing failure log and the actual output route before any further package recovery. The mixture launcher adds explicit Abracadabra, OmniAudio, and SSH actions. These are staged launchers, not verified installations on a device.

## Run

Paste the complete `tools/GAIA_AUDIO_MIXTURE_v5.0.4.sh` into Bash, or download it and run:

```bash
bash GAIA_AUDIO_MIXTURE_v5.0.4.sh diagnose
```

The default action is `diagnose`. It self-saves both functions, preserves changed prior script copies, uses private reports under `${AE:-$HOME/Æ}/logs`, and copies the runnable script to writable Termux Downloads or its local Downloads directory. It collects the latest v5.0.3 recovery error, package state, Android API availability, media volume, installed output modules, and the live PulseAudio default sink. Queries have six-second time limits. It does not play or record audio, install packages, restart the server, change volume, or load output modules. `DIAGNOSTIC_COMPLETE` means the report was collected; it does not mean playback works.

## Read the report

| Evidence | Interpretation |
| --- | --- |
| Nonempty `PACKAGE_AUDIT` | Package state still needs investigation. Preserve the original dpkg error. |
| `PULSE_ENDPOINT` fails | The requested PulseAudio endpoint is unavailable; a running daemon alone is insufficient. |
| A default sink provided by `module-null-sink` | Audio can reach a virtual sink without reaching a speaker. |
| Default sink is muted or has zero volume | The current route is silent at the PulseAudio layer. |
| Android API query times out or returns an error | Inspect the API application, permissions, and returned error on the device. A timeout alone does not establish its cause. |
| Playback process succeeds but a physical challenge is unmatched | Sound was not detected by that measurement. This does not establish broken speaker hardware. |

Termux's inspected package build installs OpenSL ES and AAudio sinks and includes an Android 8+ AAudio workaround. This diagnostic observes installed modules and configuration; it does not assume that workaround is appropriate for the current failure.

## Component roles

The working interpretation is `notexactlyawe/abracadabra` and `NexaAI/OmniAudio-2.6B`. The names are not confirmed by the user, and other projects with the OmniAudio name exist.

| Component | Role | Entry point | Execution gate |
| --- | --- | --- | --- |
| Existing v5.0.2 feedback checker | Fresh Fourier challenge and physical microphone measurement | `GAIA_AUDIO_FEEDBACK_v5.0.2.sh --check --backend termux` | Actual capture/playback route and explicit physical-mic declaration in the checker |
| Abracadabra | Register and identify supplied audio files | `abracadabra register FILE` / `abracadabra recognise FILE` | Installed CLI and working temporal fingerprint function |
| OmniAudio-2.6B | Interpret audio into text | `omniaudio` | A compatible installed Nexa runtime and model weights |
| SSH | Open the user's existing session | `ssh SSH_ARGUMENTS` | Supplied reachable destination, host verification and local credentials |

For example, after prerequisites are verified:

```bash
bash GAIA_AUDIO_MIXTURE_v5.0.4.sh abracadabra register reference.wav
bash GAIA_AUDIO_MIXTURE_v5.0.4.sh abracadabra recognise captured.wav
bash GAIA_AUDIO_MIXTURE_v5.0.4.sh omniaudio
bash GAIA_AUDIO_MIXTURE_v5.0.4.sh ssh -p PORT USER@HOST
```

Abracadabra's database is isolated under the local AE state directory. Registration backs up an existing SQLite database and holds a directory lock; a stale lock requires inspection. Each supplied-file operation has a two-minute bound. It does not use upstream `--listen`, which would select a separate microphone backend. Both identification and language-model outputs remain auxiliary and always carry `acoustic_playback_verified=false`. They cannot promote a physical playback receipt.

The inspected Abracadabra commit `ac8e080ae2ba4c582eb5842139ab7e5082b4cff0` calculates the time delta as `p2[1]-p2[1]`, always zero. The launcher checks that two different deltas produce different hashes and blocks this implementation. No library was silently patched or installed. Repairing and testing a compatible library remains required.

The model card documents the legacy `nexa run omniaudio -st` command. Its SDK link now redirects to `qualcomm/GenieX`, whose current documented platform requirements differ from the legacy SDK. The launcher calls a pre-existing compatible `nexa` executable only when explicitly requested; that SDK may download weights. It does not install a moving SDK or claim current Windows/Termux compatibility.

SSH forwards supplied arguments directly to OpenSSH, without eval or credential capture. It does not configure a server, open a firewall, guess an account, or accept a changed host key. No SSH connection has been established from the authoring workspace.

## Evidence and rollback

See `audio_mixture_verification_v5.0.4.json` for seven real authoring-host checks. Physical audio, actual Abracadabra identification, OmniAudio inference, and remote SSH remain unrun. Private reports, captures, credentials and model weights are excluded from the repository.

Restore a saved `.backup.*` script if needed. Restore a fingerprint database from its SQLite backup with the recognizer stopped and the lock inspected. v5.0.1–v5.0.3 source is preserved without modification. This release has not repaired the user's playback failure.

## Primary sources

- [Abracadabra source inspected at a fixed commit](https://github.com/notexactlyawe/abracadabra/tree/ac8e080ae2ba4c582eb5842139ab7e5082b4cff0)
- [OmniAudio-2.6B model card](https://huggingface.co/NexaAI/OmniAudio-2.6B)
- [Current SDK destination](https://github.com/qualcomm/GenieX)
- [Termux PulseAudio package build](https://github.com/termux/termux-packages/blob/master/packages/pulseaudio/build.sh)
- [PulseAudio modules](https://www.freedesktop.org/wiki/Software/PulseAudio/Documentation/User/Modules/)
