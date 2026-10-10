# Fourier speaker feedback v5.0.2

This adds a bounded speaker-to-air-to-microphone measurement loop to the v5.0.1 audio pipe. A new tone sequence goes to the playback process through stdin. The microphone capture returns through a raw PCM pipe, or through a short Termux AAC recording decoded by FFmpeg. A sliding Fourier transform checks whether the expected tones came back. The loop repeats with a fresh sequence and stops after two successful challenges, with three attempts at most.

The checker measures the probes during each check. It does not certify every later audio chunk, decode steganographic metadata, authenticate a speaker, or establish that arbitrary bytes played by the original script are meaningful audio.

## Install and run

The installer contains the complete Python source and requires Bash and Python 3.10+. It installs under `${AE:-$HOME/Æ}`, backs up a changed prior installation, writes source metadata and an activity log, and saves a Python copy to Downloads when available. It installs without downloading packages or opening a microphone. `--check` installs and then starts the measurement.

```bash
bash GAIA_AUDIO_FEEDBACK_v5.0.2.sh
"${AE:-$HOME/Æ}/bin/gaia-speaker-check" check --backend auto --physical-mic
```

Use `--physical-mic` when the selected microphone is physically exposed to sound from the intended speaker. The flag records this operator declaration; it cannot establish hardware identity. Place that microphone near the speaker, select the intended output route, and set a modest audible playback volume. The digital probe peak defaults to 0.03 of full scale and is capped at 0.05. Digital amplitude is not a calibrated sound-pressure level.

| Environment | Capture path | Playback path | Requirements |
| --- | --- | --- | --- |
| Linux PulseAudio or compatible server | `pacat --record` raw PCM stdout | `pacat --playback` PCM stdin | `pactl`, `pacat`, one hardware source or explicit `--source` |
| Linux ALSA | `arecord` raw PCM stdout | `aplay` PCM stdin | `arecord`, `aplay`, explicit `hw:N,D` or `plughw:N,D` microphone |
| Android Termux | Termux:API MIC recording, then FFmpeg PCM stdout | `pacat --playback` PCM stdin | Termux:API Android app and package, microphone access, `ffmpeg`, `pulseaudio`, running server |

On Termux, the Android Termux:API app must come from a distribution compatible with the installed Termux app. Install the CLI packages and start the audio server if it is not already running:

```bash
pkg install python termux-api ffmpeg pulseaudio
pulseaudio --check || pulseaudio --start --exit-idle-time=-1
bash GAIA_AUDIO_FEEDBACK_v5.0.2.sh --check --backend termux
```

The Termux API records a finite file; it does not expose raw microphone PCM as a Unix stdout stream. The checker confirms that its own recording started, plays the probe, stops only its own recording, then decodes its file into PCM for analysis. An existing microphone recording blocks the check and is retained. This is a bounded measurement loop rather than continuous Android microphone streaming.

PulseAudio source selection:

```bash
pactl --format=json list sources
"${AE:-$HOME/Æ}/bin/gaia-speaker-check" check --backend pulse \
  --source alsa_input.YOUR_MICROPHONE --physical-mic
```

If exactly one hardware source is observed, `--source` can be omitted. Monitor, null, loopback and known echo-cancel sources are rejected. A digital sink monitor can return exact playback samples even when no physical speaker produces sound. A virtualized device or electrical feed presented as hardware remains beyond the route filter's ability to authenticate.

ALSA selection:

```bash
arecord -l
"${AE:-$HOME/Æ}/bin/gaia-speaker-check" check --backend alsa \
  --source plughw:0,0 --sink default --physical-mic
```

Replace `plughw:0,0` with the actual microphone card/device. The checker reads the card ID and driver module and rejects `snd_aloop` / ALSA Loopback. An unknown hardware route blocks the ALSA check. It does not change mixer settings. `--sink` can select a particular output on any backend.

## Pipe-through interface

All checker PCM is signed 16-bit little-endian, 16,000 Hz, mono. The earlier stream adapter defaults to 44,100 Hz stereo; override both values for these probes.

```bash
feedback="${AE:-$HOME/Æ}/bin/gaia-speaker-check"
audio="${AE:-$HOME/Æ}/bin/gaia-audio"
"$feedback" create --spec probe.json
"$feedback" emit --spec probe.json \
  | "$audio" --backend pulse --rate 16000 --channels 1
```

This playback pipe alone proves no acoustic result. Start a physical microphone capture before emitting the probe, retain enough leading baseline and the complete sequence, and send the capture to the analyzer:

```bash
cat microphone-capture.pcm | "$feedback" analyze --spec probe.json
# Termux file bridge:
ffmpeg -v error -i microphone-recording.m4a -t 20 \
  -f s16le -ar 16000 -ac 1 pipe:1 \
  | "$feedback" analyze --spec probe.json
```

The standalone analyzer always returns `acoustic_playback_verified: false`, even for a perfect frequency match. It can observe the signal in bytes, but cannot determine how those bytes were acquired. The integrated `check` command manages capture-before-playback, fresh repeated probes, route observations and the conditional acoustic receipt.

Do not pipe captured microphone audio back into the speaker. The feedback is a measurement/control loop: probe, measure, evaluate, repeat. Feeding microphone samples into playback would create a separate acoustic amplification loop.

To use the check before the original 44.1 kHz stereo workflow:

```bash
set -o pipefail
"${AE:-$HOME/Æ}/bin/gaia-speaker-check" check --backend auto --physical-mic \
  && "${AE:-$HOME/Æ}/bin/gaia-audio" --backend auto < stream.pcm
```

That establishes a successful probe check immediately before the stream. Playback may subsequently change; ongoing verification would need repeated probes or synchronized comparison with the actual program audio.

## Detector parameters and evidence

Each probe lasts 4.84 seconds: 0.6 seconds of baseline silence, twelve 0.20-second tones separated by 0.12-second gaps, and 0.4 seconds of trailing silence. Eight frequencies from 671.875 to 3484.375 Hz appear in a fresh shuffled order, followed by four additional tones. Adjacent tones differ. A random nonce determines the reproducible probe waveform and accompanies the receipt; the frequency detector does not authenticate the nonce cryptographically.

The analyzer removes DC, applies a 1024-sample Hann window, and advances 256 samples per FFT at 16 kHz. Windows span 64 milliseconds, hops span 16 milliseconds, and frequency bins are 15.625 Hz apart. It sums the expected bin and its two neighbors, estimates off-band noise, and compares the expected tone against other challenge bands and the pre-tone room baseline.

A successful challenge requires at least 11 of 12 tones with the expected dominant frequency, at least 10 gaps with a 3 dB energy drop, and no more than 0.5% clipped samples. Each accepted tone must exceed other probe bands by 3 dB, off-band noise by 10 dB, its baseline band by 6 dB, and the minimum digital band level of -70 dB relative to full scale. These are initial software thresholds, not measured false-positive/false-negative rates for a device or room.

The analyzer searches up to two seconds of leading alignment delay by default (`--max-lag 0..3`). This includes capture startup, playback buffering and codec delays. It is not a calibrated acoustic propagation time and must not be converted into speaker distance. Frequency-dependent room response, reverberation, quiet output, automatic gain control, noise suppression or echo cancellation can cause a missed probe. A missed probe means `not_verified`; it does not diagnose a broken speaker.

`check` writes one final JSON receipt to stdout and progress/results to stderr. Exit codes: 0 for two matching challenges, 2 for a completed check without enough matches, 1 for blocked prerequisites or failed transport, 130/143 for interruption. The standalone analyzer uses 0 for a signal match and 2 for no match while always leaving acoustic verification false.

Microphone audio, probe specifications and receipts stay in a private session directory below `${AE:-$HOME/Æ}/logs/audio-feedback-v5.0.2`. Captures are bounded to 20 seconds each and are never uploaded by this code. A locked, append-only SHA-256 hash chain records completed checks in a separate `audio_feedback_v5.0.2.jsonl` file. It detects accidental edits or changes relative to a retained head; it is neither a signature nor protection against someone rewriting an entire unanchored chain.

## Verification boundary

The software checks exercise an independent DFT comparison, known signal fixtures, negative fixtures, an actual emit/analyze OS pipe, actual FFmpeg AAC encode/decode, process deadlines, capture byte limits, stderr pressure, source-metadata rejection, concurrent journal processes, journal tampering, interruption and installer retention. Generated signals and codec round-trips are algorithm and transport evidence only.

No physical microphone or speaker is available in the authoring workspace. ALSA, PulseAudio and Termux device runs remain unperformed. See [verification report](audio_feedback_verification_v5.0.2.json) for measured software results and explicit hardware gates.

Primary references: [STFT definition and window/hop semantics](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.ShortTimeFFT.html), [PulseAudio null sinks, monitors and echo cancellation](https://wiki.freedesktop.org/www/Software/PulseAudio/Documentation/User/Modules/), [Termux microphone command](https://github.com/termux/termux-api-package/blob/master/scripts/termux-microphone-record.in), [Termux MIC recording implementation](https://github.com/termux/termux-api/blob/master/app/src/main/java/com/termux/api/apis/MicRecorderAPI.java), [Termux API installation](https://github.com/termux/termux-api#installation), [ALSA playback/record testing](https://www.alsa-project.org/wiki/SoundcardTesting).
