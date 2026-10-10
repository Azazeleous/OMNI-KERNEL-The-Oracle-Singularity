# OMNI-KERNEL audio-stream adapter v5.0.1

The submitted stream handler is preserved in `archive/sources/audio_stream_user_v0.py`.
The working adapter is `runtime/gaia_audio_stream_v5.0.1.py`. It forwards real PCM,
counts received and submitted bytes separately, retains frame boundaries across
short reads, and records timestamped session receipts in a locked hash chain.
It does not extract metadata, create embedding vectors, or implement steganography.

The input contract is **raw interleaved signed 16-bit little-endian PCM**. Defaults
are 44,100 Hz and two channels: four bytes per PCM frame. JSON, MP3 and WAV
containers are not raw PCM. Convert encoded audio before forwarding it, for example
with an installed FFmpeg: `ffmpeg -i input.wav -f s16le -ar 44100 -ac 2 -`.

## Install and use

Python 3.10+ and Bash are required on Linux or Termux. Run the self-contained
installer from the checked-out repository:

```bash
bash tools/GAIA_AUDIO_STREAM_v5.0.1.sh
```

It saves the adapter under `${AE:-$HOME/Æ}/autonomous`, adds a launcher under
the same root's `bin`, backs up differing existing files, records an installation
fingerprint, and copies the adapter to accessible Downloads. It does not download
packages or start audio playback. The script's inline source is the same byte
sequence as the standalone Python artifact.

Choose a backend explicitly when the available audio server matters:

```bash
"${AE:-$HOME/Æ}/bin/gaia-audio" --backend alsa < stream.pcm
"${AE:-$HOME/Æ}/bin/gaia-audio" --backend pulse < stream.pcm
"${AE:-$HOME/Æ}/bin/gaia-audio" --backend record --output retained.pcm < stream.pcm
```

`alsa` needs the installed `aplay` binary and an accessible ALSA device. `pulse`
needs `pacat` and an accessible running PulseAudio-compatible server; this is the
intended Termux path. Availability on the Samsung A15 has not been checked.
`record` writes an exclusive new PCM file and refuses to overwrite an existing
file. It is real recording, with no playback. `auto` chooses an installed `pacat`
first, otherwise `aplay`; connection failure is reported without a silent fallback.

Audio never goes to stdout. Drain the JSON telemetry on stderr when invoking
the adapter from another process. Child stderr is continuously drained with a
4 KiB diagnostic tail, and child stdout is discarded. Write stalls, draining and
ledger lock acquisition have bounds. SIGINT and SIGTERM retain cancelled receipts
and return 130 and 143. Broken pipes, failed child exits, truncated frames, checksum
mismatches and corrupt ledgers fail with a nonzero exit status. Partial recordings
remain available for inspection after failure; they are not promoted as complete.

## Evidence and integrity boundaries

`bytes_submitted` and `submitted_sha256` measure bytes accepted by the pipe or file.
They do not prove that a DAC consumed the data or that a speaker emitted sound.
Successful process exit is recorded independently. Every receipt explicitly sets
`source_authenticated` and `acoustic_playback_verified` to false.

`--expect-sha256 HEX` compares the complete received input at EOF. This is a checksum
comparison, without source authentication. Audio already submitted before EOF cannot
be recalled if the checksum differs. Use a separate authenticated, complete-file
validation step before playback when that is a requirement.

One final receipt per session is appended to the separate audio journal at
`${AE:-$HOME/Æ}/logs/audio_stream_v5.0.1.jsonl`. It is not automatically synchronized
with the v5.0.0 SQLite ledger. The chain is verified before sink creation and again
under an exclusive lock before append. Owners can rewrite an entire chain; retain
its exported head independently to detect replacement. No encryption or signature
is claimed. Audio samples, credentials and raw chat are not stored in telemetry.

## Verification and rollback

```bash
python3 -m unittest discover -s tests -p test_audio_stream_v5.py -v
```

The suite exercises actual PCM files, OS pipes, subprocess stderr pressure, blocked
pipe and drain timeouts, reaping, SIGTERM, filesystem preservation, checksum errors,
corruption rejection, real held locks and concurrent processes. Fault injection is
local transport evidence and is not a sound-device test. See
`docs/audio_verification_v5.0.1.json` for observed outcomes and missing gates.

For local rollback, restore a saved `.backup.TIMESTAMP.PID` file to the exact
adapter or launcher path shown by the installer. If there was no previous adapter,
remove only the new launcher and versioned adapter. Retain recordings, journals,
backup files and older versions. Repository rollback can use a new `git revert`
commit for the audio release rather than resetting unrelated history.

The next playback checkpoint is a real compatible source streamed on the intended
host, with exit status zero, equal input/submitted hashes, a durable completed
receipt and an independent observation of audible output. A completed receipt
alone satisfies the software transport gate, not the acoustic gate.
