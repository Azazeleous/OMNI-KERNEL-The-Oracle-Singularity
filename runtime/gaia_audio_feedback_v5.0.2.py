#!/usr/bin/env python3
"""[SS][TDOC-AUDIO-FEEDBACK-V5.0.2] Bounded speaker -> air -> microphone test.

Pure-Python windowed FFT; raw S16_LE mono at 16 kHz. No live hardware claim
can be made by the standalone analyze command. check requires a physical
microphone declaration, an observed capture route and fresh repeated probes.
"""
import argparse
from array import array
import bisect
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import select
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time

VERSION = "5.0.2"
RATE, NFFT, HOP = 16000, 1024, 256
BINS = (43, 59, 79, 101, 127, 157, 191, 223)
MAX_BYTES = RATE * 2 * 20
SPEC_FIELDS = {"version", "nonce", "rate", "fft", "bins", "order", "hold", "gap", "lead", "tail", "amplitude"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def new_spec(amplitude=0.03):
    nonce = secrets.token_hex(16)
    rng = random.Random(int(nonce, 16))
    order = list(range(len(BINS)))
    rng.shuffle(order)
    for _ in range(4):
        order.append(rng.choice([x for x in range(len(BINS)) if x != order[-1]]))
    return {"version": VERSION, "nonce": nonce, "rate": RATE, "fft": NFFT,
            "bins": list(BINS), "order": order, "hold": 0.2, "gap": 0.12,
            "lead": 0.6, "tail": 0.4, "amplitude": amplitude}


def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) != SPEC_FIELDS:
        raise ValueError("Invalid probe specification fields")
    if spec["version"] != VERSION or spec["rate"] != RATE or spec["fft"] != NFFT or spec["bins"] != list(BINS):
        raise ValueError("Unsupported probe format")
    if not isinstance(spec["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", spec["nonce"]):
        raise ValueError("Invalid challenge nonce")
    if not isinstance(spec["order"], list) or len(spec["order"]) != 12 or any(type(x) is not int or not 0 <= x < 8 for x in spec["order"]):
        raise ValueError("Invalid frequency order")
    if set(spec["order"][:8]) != set(range(8)) or any(a == b for a, b in zip(spec["order"], spec["order"][1:])):
        raise ValueError("Challenge requires all eight frequencies and separated adjacent tones")
    if any(spec[k] != v for k, v in {"hold": 0.2, "gap": 0.12, "lead": 0.6, "tail": 0.4}.items()):
        raise ValueError("Unsupported probe timing")
    if type(spec["amplitude"]) not in (int, float) or not math.isfinite(spec["amplitude"]) or not 0.005 <= spec["amplitude"] <= 0.05:
        raise ValueError("Digital peak amplitude must be 0.005-0.05")
    return spec


def probe_pcm(spec):
    validate_spec(spec)
    values = array("h", [0]) * round(spec["lead"] * RATE)
    count = round(spec["hold"] * RATE)
    ramp = round(0.01 * RATE)
    rng = random.Random(int(spec["nonce"], 16))
    for index in spec["order"]:
        phase = rng.random() * 2 * math.pi
        frequency = BINS[index] * RATE / NFFT
        for k in range(count):
            envelope = min(1, k / ramp, (count - 1 - k) / ramp)
            values.append(round(32767 * spec["amplitude"] * envelope * math.sin(2 * math.pi * frequency * k / RATE + phase)))
        values.extend([0] * round(spec["gap"] * RATE))
    values.extend([0] * round(spec["tail"] * RATE))
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def fft(values):
    """Forward radix-two FFT; values must have a power-of-two length."""
    out = [complex(x) for x in values]
    size = len(out)
    if size < 2 or size & (size - 1):
        raise ValueError("FFT length must be a power of two")
    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    length = 2
    while length <= size:
        root = complex(math.cos(-2 * math.pi / length), math.sin(-2 * math.pi / length))
        for start in range(0, size, length):
            w = 1 + 0j
            for k in range(length // 2):
                a, b = out[start + k], w * out[start + k + length // 2]
                out[start + k], out[start + k + length // 2] = a + b, a - b
                w *= root
        length *= 2
    return out


def db_ratio(a, b=1):
    return 10 * math.log10(max(a, 1e-18) / max(b, 1e-18))


def analyze(raw, spec, max_lag=2):
    validate_spec(spec)
    if not math.isfinite(max_lag) or not 0 <= max_lag <= 3:
        raise ValueError("Maximum lag must be 0-3 seconds")
    if len(raw) > MAX_BYTES or len(raw) % 2:
        raise ValueError("Capture exceeds 20 seconds or has an incomplete PCM sample")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    duration = len(probe_pcm(spec)) / (RATE * 2)
    if len(samples) < round(duration * RATE):
        raise ValueError("Capture is too short for a complete challenge")
    window = [0.5 - 0.5 * math.cos(2 * math.pi * k / (NFFT - 1)) for k in range(NFFT)]
    scale = 4 / sum(window) ** 2
    excluded = {k for b in BINS for k in range(b - 2, b + 3)}
    times, bands, floors = [], [], []
    for start in range(0, len(samples) - NFFT + 1, HOP):
        chunk = samples[start:start + NFFT]
        mean = sum(chunk) / NFFT
        spectrum = fft([(x - mean) / 32768 * w for x, w in zip(chunk, window)])
        power = [(x.real * x.real + x.imag * x.imag) * scale for x in spectrum[:NFFT // 2]]
        bands.append([sum(power[b - 1:b + 2]) for b in BINS])
        floors.append(3 * statistics.median(power[k] for k in range(20, 240) if k not in excluded))
        times.append((start + NFFT / 2) / RATE)
    clipping = sum(abs(x) >= 32760 for x in samples) / len(samples)
    best = None
    period = spec["hold"] + spec["gap"]
    for tick in range(round(max_lag * RATE / HOP) + 1):
        lag = tick * HOP / RATE
        baseline_ids = [i for i, t in enumerate(times) if 0.06 <= t < lag + spec["lead"] - 0.08]
        if len(baseline_ids) < 3:
            continue
        baseline = [statistics.median(bands[i][j] for i in baseline_ids) for j in range(8)]
        metrics, matches, drops = [], 0, 0
        for step, target in enumerate(spec["order"]):
            begin = lag + spec["lead"] + step * period
            lo = bisect.bisect_left(times, begin + 0.045)
            hi = bisect.bisect_right(times, begin + spec["hold"] - 0.045)
            if hi - lo < 2:
                break
            levels = [statistics.median(b[j] for b in bands[lo:hi]) for j in range(8)]
            noise = statistics.median(floors[lo:hi])
            winner = max(range(8), key=levels.__getitem__)
            margin = db_ratio(levels[target], max(levels[j] for j in range(8) if j != target))
            snr, gain = db_ratio(levels[target], noise), db_ratio(levels[target], baseline[target])
            gap_center = begin + spec["hold"] + spec["gap"] / 2
            gap_index = min(range(max(0, bisect.bisect_left(times, gap_center) - 1),
                                  min(len(times), bisect.bisect_left(times, gap_center) + 1)),
                            key=lambda i: abs(times[i] - gap_center)) if gap_center <= times[-1] else None
            drop = db_ratio(levels[target], bands[gap_index][target]) if gap_index is not None else -180
            matched = winner == target and margin >= 3 and snr >= 10 and gain >= 6 and db_ratio(levels[target]) >= -70
            matches += int(matched)
            drops += int(drop >= 3)
            metrics.append({"expected_hz": BINS[target] * RATE / NFFT,
                            "observed_hz": BINS[winner] * RATE / NFFT,
                            "snr_db": round(snr, 2), "baseline_gain_db": round(gain, 2),
                            "winner_margin_db": round(margin, 2), "gap_drop_db": round(drop, 2),
                            "matched": matched})
        if len(metrics) != 12:
            continue
        quality = (matches, drops, statistics.median(x["snr_db"] for x in metrics))
        if best is None or quality > best[0]:
            best = (quality, lag, metrics)
    if best is None:
        raise ValueError("Capture does not contain a complete search interval")
    quality, lag, metrics = best
    detected = quality[0] >= 11 and quality[1] >= 10 and clipping <= 0.005
    return {"version": VERSION, "nonce": spec["nonce"], "status": "challenge_detected" if detected else "not_detected",
            "signal_detected": detected, "matched_steps": quality[0], "total_steps": 12,
            "gap_drops": quality[1], "alignment_seconds": round(lag, 4),
            "median_snr_db": quality[2], "clipping_fraction": round(clipping, 6),
            "capture_seconds": len(samples) / RATE, "input_sha256": sha(raw),
            "probe_sha256": sha(probe_pcm(spec)), "steps": metrics,
            "acoustic_playback_verified": False,
            "evidence_scope": "Signal analysis only; a PCM pipe does not establish a physical acoustic route"}


def executable(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Missing prerequisite: {name}")
    return found


def command(args, timeout=8, data=None):
    proc = subprocess.Popen(args, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = proc.communicate(input=data, timeout=timeout)
    except BaseException:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate(timeout=2)
        raise
    if proc.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed ({proc.returncode}): " + err[-2000:].decode(errors="replace"))
    return out


def pulse_sources():
    sources = json.loads(command([executable("pactl"), "--format=json", "list", "sources"]))
    if not isinstance(sources, list):
        raise ValueError("pactl did not return a source inventory")
    return sources


def physical_pulse_source(source):
    if not isinstance(source, dict) or not isinstance(source.get("name"), str):
        return False
    name = source.get("name", "").lower()
    props = source.get("properties", {})
    if not isinstance(props, dict) or "monitor_of_sink" not in source:
        return False
    monitor = source.get("monitor_of_sink")
    return (monitor in (None, -1, 4294967295, "n/a") and
            not any(x in name for x in ("monitor", "loopback", "null", "echo-cancel")) and
            (name.startswith("alsa_input.") or props.get("device.api") in ("alsa", "sles", "opensles")))


class Capture:
    """Bounded real PCM source with concurrently drained diagnostics."""
    def __init__(self, cmd, seconds):
        if not math.isfinite(seconds) or not 0 < seconds <= 20:
            raise ValueError("Capture deadline must be 0-20 seconds")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.data, self.tail = bytearray(), bytearray()
        self.ready, self.stop = threading.Event(), threading.Event()
        self.error, self.intentional_stop = None, False
        self.seconds = seconds
        self.worker = threading.Thread(target=self._read, daemon=True)
        self.worker.start()

    def _read(self):
        streams = {self.proc.stdout.fileno(): "pcm", self.proc.stderr.fileno(): "stderr"}
        deadline = time.monotonic() + self.seconds
        try:
            while streams and not self.stop.is_set() and time.monotonic() < deadline:
                for fd in select.select(list(streams), [], [], 0.1)[0]:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        del streams[fd]
                    elif streams[fd] == "stderr":
                        self.tail.extend(chunk)
                        del self.tail[:-4096]
                    else:
                        self.data.extend(chunk)
                        if len(self.data) > MAX_BYTES:
                            raise ValueError("Capture exceeded the 20-second byte limit")
                        if len(self.data) >= 2048:
                            self.ready.set()
            if self.proc.poll() is None and (self.stop.is_set() or time.monotonic() >= deadline):
                self.intentional_stop = True
                self._signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._signal(signal.SIGKILL)
                self.proc.wait(timeout=2)
                raise RuntimeError("Capture did not terminate within its bound")
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.error = str(exc)
            if self.proc.poll() is None:
                self._signal(signal.SIGKILL)
                self.proc.wait(timeout=2)
        finally:
            self.proc.stdout.close()
            self.proc.stderr.close()
            self.ready.set()

    def finish(self):
        self.stop.set()
        self.worker.join(timeout=5)
        if self.worker.is_alive():
            self._signal(signal.SIGKILL)
            self.proc.wait(timeout=2)
            raise RuntimeError("Capture reader did not finish")
        allowed = self.proc.returncode == 0 or (self.intentional_stop and self.proc.returncode == -signal.SIGTERM)
        if self.error or not allowed:
            raise RuntimeError(self.error or self.tail.decode(errors="replace") or "Capture source failed")
        return bytes(self.data)

    def _signal(self, signum):
        try:
            os.killpg(self.proc.pid, signum)
        except ProcessLookupError:
            pass


def termux_info():
    info = json.loads(command([executable("termux-microphone-record"), "-i"]))
    if not isinstance(info, dict) or type(info.get("isRecording")) is not bool:
        raise ValueError("Termux microphone status was not valid JSON")
    return info


def journal(path, receipt=None, lock_timeout=5):
    """Verify before capture; lock and verify again before a durable append."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR, 0o600), "r+b") as stream:
        deadline = time.monotonic() + lock_timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TimeoutError("Feedback receipt lock timeout")
                time.sleep(0.02)
        head, seq = "0" * 64, 0
        while True:
            line = stream.readline(1024 * 1024 + 1)
            if not line:
                break
            seq += 1
            if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                raise ValueError("Feedback ledger line is oversized or incomplete")
            item = json.loads(line)
            if not isinstance(item, dict) or set(item) != {"seq", "timestamp", "kind", "payload", "prev", "hash"}:
                raise ValueError("Feedback ledger has invalid fields")
            body = {k: item[k] for k in ("seq", "timestamp", "kind", "payload", "prev")}
            if type(item["seq"]) is not int or item["seq"] != seq or item["prev"] != head or item["hash"] != sha(canonical(body).encode()):
                raise ValueError("Feedback ledger failed integrity verification")
            head = item["hash"]
        if receipt is not None:
            body = {"seq": seq + 1, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "kind": "AUDIO_FEEDBACK", "payload": receipt, "prev": head}
            head = sha(canonical(body).encode())
            stream.write((canonical({**body, "hash": head}) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        return head


def live_check(args):
    if not args.physical_mic:
        raise ValueError("Use --physical-mic only for a microphone exposed to the speaker's sound")
    root = Path(args.state_dir).expanduser().resolve()
    ledger = root / "audio_feedback_v5.0.2.jsonl"
    journal(ledger)
    backend = args.backend
    if backend == "auto":
        backend = "termux" if shutil.which("termux-microphone-record") else ("pulse" if shutil.which("pactl") else "alsa")
    if backend == "pulse":
        sources = [s for s in pulse_sources() if physical_pulse_source(s)]
        matches = [s for s in sources if not args.source or s["name"] == args.source]
        if len(matches) != 1:
            raise ValueError("Select one physical microphone with --source; monitor/virtual sources are rejected")
        source = matches[0]["name"]
        capture_cmd = [executable("pacat"), "--record", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1", f"--device={source}"]
        play_cmd = [executable("pacat"), "--playback", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1"]
        if args.sink:
            play_cmd.append(f"--device={args.sink}")
        route = {"backend": backend, "source": source, "monitor_rejected": True}
    elif backend == "alsa":
        if not args.source or not re.fullmatch(r"(?:plug)?hw:[0-9]+,[0-9]+(?:,[0-9]+)?", args.source):
            raise ValueError("ALSA requires a hardware microphone --source such as plughw:0,0")
        card = args.source.split(":", 1)[1].split(",")[0]
        module = Path(f"/sys/class/sound/card{card}/device/driver/module").resolve(strict=True).name
        card_id = Path(f"/proc/asound/card{card}/id").read_text().strip()
        if "loopback" in card_id.lower() or module == "snd_aloop":
            raise ValueError("ALSA Loopback is a transport route, not an acoustic microphone")
        capture_cmd = [executable("arecord"), "-q", "-N", "-D", args.source, "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1"]
        play_cmd = [executable("aplay"), "-q", "-N", "-D", args.sink or "default", "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1"]
        route = {"backend": backend, "source": args.source, "card_id": card_id, "driver_module": module}
    else:
        if args.source:
            raise ValueError("Termux:API uses its MIC source; --source applies to Linux capture only")
        executable("ffmpeg")
        if termux_info()["isRecording"]:
            raise RuntimeError("An existing Termux microphone recording is active; it was left unchanged")
        play_cmd = [executable("pacat"), "--playback", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1"]
        if args.sink:
            play_cmd.append(f"--device={args.sink}")
        route = {"backend": backend, "source": "Termux:API MediaRecorder MIC", "mic_source_default": "MIC"}
    directory = root / ("session-" + secrets.token_hex(8))
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    runs = []
    needed = 2
    for iteration in range(args.loops):
        spec = new_spec(args.amplitude)
        pcm = probe_pcm(spec)
        duration = len(pcm) / (RATE * 2)
        prefix = directory / f"probe-{iteration + 1}"
        Path(str(prefix) + ".json").write_text(canonical(spec) + "\n")
        Path(str(prefix) + ".pcm").write_bytes(pcm)
        print(canonical({"status": "capturing", "iteration": iteration + 1, "nonce": spec["nonce"], "route": route}), file=sys.stderr, flush=True)
        capture, owned_recording = None, None
        try:
            if backend == "termux":
                owned_recording = str(Path(str(prefix) + ".m4a").resolve())
                command([executable("termux-microphone-record"), "-f", owned_recording,
                         "-l", str(math.ceil(duration + args.max_lag + 2)), "-e", "aac", "-r", str(RATE), "-c", "1"])
                info = termux_info()
                if not info["isRecording"] or info.get("outputFile") != owned_recording:
                    raise RuntimeError("Termux did not confirm ownership of the requested microphone recording")
                time.sleep(0.35)
            else:
                capture = Capture(capture_cmd, duration + args.max_lag + 3)
                if not capture.ready.wait(timeout=3) or len(capture.data) < 2048:
                    raise RuntimeError("Microphone produced no PCM within the startup timeout")
            command(play_cmd, timeout=duration + 5, data=pcm)
            time.sleep(0.6)
            if backend == "termux":
                info = termux_info()
                if info["isRecording"]:
                    if info.get("outputFile") != owned_recording:
                        raise RuntimeError("Microphone ownership changed; the other recording was left unchanged")
                    command([executable("termux-microphone-record"), "-q"])
                owned_recording = None
                raw = command([executable("ffmpeg"), "-v", "error", "-i", str(prefix) + ".m4a", "-t", "20", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "pipe:1"], timeout=12)
            else:
                raw = capture.finish()
                capture = None
            Path(str(prefix) + "-capture.pcm").write_bytes(raw)
            evidence = analyze(raw, spec, args.max_lag)
            evidence.update(iteration=iteration + 1, route=route, playback_exit_code=0,
                            capture_route_declaration="operator_declared_physical_microphone")
            runs.append(evidence)
            print(canonical(evidence), file=sys.stderr, flush=True)
        finally:
            if capture is not None:
                capture.finish()
            if owned_recording:
                info = termux_info()
                if info["isRecording"] and info.get("outputFile") == owned_recording:
                    command([executable("termux-microphone-record"), "-q"])
        if sum(r["signal_detected"] for r in runs) >= needed:
            break
    passed = sum(r["signal_detected"] for r in runs) >= needed
    receipt = {"version": VERSION, "status": "acoustic_challenge_verified" if passed else "not_verified",
               "acoustic_playback_verified": passed, "required_passes": needed,
               "passes": sum(r["signal_detected"] for r in runs), "runs": runs,
               "route": route, "capture_route_declaration": "operator_declared_physical_microphone",
               "evidence_scope": "Fresh probes returned through the declared microphone route; not cryptographic hardware attestation, SPL calibration or speaker identity authentication",
               "recordings_directory": str(directory)}
    receipt["ledger_head"] = journal(ledger, receipt)
    Path(directory / "receipt.json").write_text(canonical(receipt) + "\n")
    return receipt


class Cancelled(KeyboardInterrupt):
    def __init__(self, signum):
        self.signum = signum


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--spec", required=True)
    create.add_argument("--amplitude", type=float, default=0.03)
    emit = sub.add_parser("emit")
    emit.add_argument("--spec", required=True)
    check = sub.add_parser("check")
    check.add_argument("--backend", choices=("auto", "termux", "pulse", "alsa"), default="auto")
    check.add_argument("--source")
    check.add_argument("--sink")
    check.add_argument("--physical-mic", action="store_true")
    check.add_argument("--loops", type=int, choices=(2, 3), default=3)
    check.add_argument("--amplitude", type=float, default=0.03)
    check.add_argument("--max-lag", type=float, default=2)
    ae = Path(os.environ.get("AE", str(Path.home() / "Æ")))
    check.add_argument("--state-dir", default=str(ae / "logs" / "audio-feedback-v5.0.2"))
    analyze_cmd = sub.add_parser("analyze")
    analyze_cmd.add_argument("--spec", required=True)
    analyze_cmd.add_argument("--max-lag", type=float, default=2)
    args = parser.parse_args(argv)
    def cancel(signum, _frame):
        raise Cancelled(signum)
    previous = {s: signal.signal(s, cancel) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        if args.action == "create":
            spec = validate_spec(new_spec(args.amplitude))
            path = Path(args.spec).expanduser()
            with path.open("x") as stream:
                stream.write(canonical(spec) + "\n")
            result = {"status": "created", "spec": str(path), "nonce": spec["nonce"]}
        elif args.action in ("emit", "analyze"):
            spec = validate_spec(json.loads(Path(args.spec).expanduser().read_text()))
            if args.action == "emit":
                sys.stdout.buffer.write(probe_pcm(spec))
                sys.stdout.buffer.flush()
                return 0
            raw = sys.stdin.buffer.read(MAX_BYTES + 1)
            result = analyze(raw, spec, args.max_lag)
        else:
            validate_spec(new_spec(args.amplitude))
            if not math.isfinite(args.max_lag) or not 0 <= args.max_lag <= 3:
                raise ValueError("Maximum lag must be 0-3 seconds")
            result = live_check(args)
        print(canonical(result), flush=True)
        return 0 if result.get("signal_detected", result.get("acoustic_playback_verified", args.action == "create")) else 2
    except KeyboardInterrupt as exc:
        print(canonical({"version": VERSION, "status": "cancelled", "acoustic_playback_verified": False}), file=sys.stderr)
        return 128 + getattr(exc, "signum", signal.SIGINT)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(canonical({"version": VERSION, "status": "blocked_or_failed", "error": str(exc), "acoustic_playback_verified": False}), file=sys.stderr)
        return 1
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
