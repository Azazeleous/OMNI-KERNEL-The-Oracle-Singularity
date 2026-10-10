#!/usr/bin/env python3
"""[SS][TDOC-AUDIO-V5.0.1] OMNI-KERNEL / The Nexus Generation.

Read raw signed 16-bit little-endian PCM from stdin. Emit JSON to stderr.
SHA-256 receipts measure bytes; they do not authenticate a source or prove sound.
Python 3.10+, Linux/Termux. No network access or metadata extraction.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

VERSION = "5.0.1"
GENESIS = "0" * 64


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def journal(path, receipt=None, lock_timeout=5):
    """Verify under a process lock; append one durable receipt per session."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "r+b") as stream:
        deadline = time.monotonic() + lock_timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Audio ledger lock timeout")
                time.sleep(0.02)
        head, seq = GENESIS, 0
        while True:
            line = stream.readline(1024 * 1024 + 1)
            if not line:
                break
            seq += 1
            if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                raise ValueError(f"Ledger line {seq}: oversized or incomplete")
            record = json.loads(line)
            fields = {"seq", "timestamp", "kind", "payload", "prev", "hash"}
            if not isinstance(record, dict) or set(record) != fields:
                raise ValueError(f"Ledger line {seq}: invalid fields")
            body = {k: record[k] for k in fields - {"hash"}}
            check = hashlib.sha256(canonical(body).encode()).hexdigest()
            if type(record["seq"]) is not int or record["seq"] != seq:
                raise ValueError(f"Ledger line {seq}: invalid sequence")
            if record["prev"] != head or record["hash"] != check:
                raise ValueError(f"Ledger line {seq}: hash-chain mismatch")
            head = check
        if receipt is not None:
            body = {"seq": seq + 1, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "kind": "AUDIO_STREAM", "payload": receipt, "prev": head}
            head = hashlib.sha256(canonical(body).encode()).hexdigest()
            stream.write((canonical({**body, "hash": head}) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        return head


class Sink:
    """A bounded pipe to a real process, or an exclusive local PCM recording."""
    def __init__(self, command=None, output=None):
        self.proc = None
        self.tail = bytearray()
        self.reader = None
        if output is not None:
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            self.stream = os.fdopen(fd, "wb", buffering=0)
        else:
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, bufsize=0,
                start_new_session=True)
            self.stream = self.proc.stdin
            os.set_blocking(self.stream.fileno(), False)
            self.reader = threading.Thread(target=self._drain_errors, daemon=True)
            self.reader.start()

    def _drain_errors(self):
        try:
            while True:
                data = self.proc.stderr.read(4096)
                if not data:
                    break
                self.tail.extend(data)
                del self.tail[:-4096]
        except (OSError, ValueError):
            pass

    def check(self):
        if self.proc is not None and self.proc.poll() is not None:
            raise RuntimeError(f"Audio sink exited before input EOF ({self.proc.returncode})")

    def write(self, data, timeout):
        """Return accepted bytes; the caller handles partial writes explicitly."""
        deadline = time.monotonic() + timeout
        while True:
            self.check()
            if self.proc is None:
                return self.stream.write(data)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Audio sink stopped accepting bytes")
            if select.select([], [self.stream.fileno()], [], min(0.2, remaining))[1]:
                try:
                    return os.write(self.stream.fileno(), data)
                except BlockingIOError:
                    continue

    def finish(self, abort, timeout):
        """Close input, wait within a bound, and reap the child on every path."""
        try:
            if not self.stream.closed:
                try:
                    if self.proc is None:
                        os.fsync(self.stream.fileno())
                finally:
                    self.stream.close()
            if self.proc is None:
                return None
            if abort and self.proc.poll() is None:
                self._signal(signal.SIGTERM)
            try:
                code = self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._signal(signal.SIGKILL)
                self.proc.wait(timeout=2)
                raise TimeoutError("Audio sink did not finish within the drain timeout")
            if not abort and code != 0:
                raise RuntimeError(f"Audio sink failed ({code})")
            return code
        finally:
            if self.proc is not None:
                if self.proc.poll() is None:
                    self._signal(signal.SIGKILL)
                    self.proc.wait(timeout=2)
                self.reader.join(timeout=1)
                if not self.reader.is_alive():
                    self.proc.stderr.close()

    def _signal(self, signum):
        try:
            os.killpg(self.proc.pid, signum)
        except ProcessLookupError:
            pass


def open_sink(args):
    backend = args.backend
    if backend == "auto":
        backend = "pulse" if shutil.which("pacat") else "alsa"
    if backend == "record":
        if not args.output or args.device:
            raise ValueError("record requires --output and does not accept --device")
        return backend, Sink(output=args.output)
    if args.output:
        raise ValueError("--output requires --backend record")
    executable = shutil.which("pacat" if backend == "pulse" else "aplay")
    if not executable:
        raise RuntimeError(f"Missing {'pacat' if backend == 'pulse' else 'aplay'}; install the chosen sink")
    if backend == "pulse":
        command = [executable, "--playback", "--raw", "--format=s16le",
                   f"--rate={args.rate}", f"--channels={args.channels}"]
        if args.device:
            command.append(f"--device={args.device}")
    else:
        command = [executable, "-q", "-N", "-t", "raw", "-f", "S16_LE",
                   "-r", str(args.rate), "-c", str(args.channels),
                   "-D", args.device or "default"]
    return backend, Sink(command=command)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("auto", "alsa", "pulse", "record"), default="auto")
    parser.add_argument("--device")
    parser.add_argument("--output", help="Exclusive new raw PCM file; record backend only")
    parser.add_argument("--rate", type=int, default=44100)
    parser.add_argument("--channels", type=int, default=2)
    parser.add_argument("--chunk-bytes", type=int, default=4096)
    parser.add_argument("--stall-timeout", type=float, default=10)
    parser.add_argument("--drain-timeout", type=float, default=10)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--expect-sha256", help="Check at EOF; previously submitted audio cannot be recalled")
    ae = Path(os.environ.get("AE", str(Path.home() / "Æ")))
    parser.add_argument("--ledger", default=str(ae / "logs" / "audio_stream_v5.0.1.jsonl"))
    args = parser.parse_args(argv)
    if not 8000 <= args.rate <= 192000 or not 1 <= args.channels <= 8:
        parser.error("rate must be 8000-192000 and channels 1-8")
    if not 1 <= args.chunk_bytes <= 1024 * 1024:
        parser.error("chunk-bytes must be 1-1048576")
    if any(not math.isfinite(v) or not 0.1 <= v <= 60 for v in
           (args.stall_timeout, args.drain_timeout, args.interval)):
        parser.error("timeouts and interval must be finite values from 0.1 to 60 seconds")
    if args.expect_sha256:
        args.expect_sha256 = args.expect_sha256.lower()
        if len(args.expect_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.expect_sha256):
            parser.error("expect-sha256 must be a 64-digit hex SHA-256")
    session = uuid.uuid4().hex
    started, received, submitted = time.monotonic(), 0, 0
    input_hash, sink_hash = hashlib.sha256(), hashlib.sha256()
    sink, backend, pending = None, args.backend, b""
    status, error, result, stop_signal = "starting", None, 0, signal.SIGINT
    ledger_valid = False

    def interrupt(signum, _frame):
        nonlocal stop_signal
        stop_signal = signum
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)

    def packet(state):
        elapsed = time.monotonic() - started
        return {"version": VERSION, "session": session, "status": state,
                "epoch": time.time(), "backend": backend, "format": "S16_LE",
                "rate": args.rate, "channels": args.channels,
                "bytes_received": received, "bytes_submitted": submitted,
                "bytes_unsubmitted": received - submitted,
                "frames_submitted": submitted // (2 * args.channels),
                "submitted_frame_remainder": submitted % (2 * args.channels),
                "pcm_seconds_submitted": submitted // (2 * args.channels) / args.rate,
                "elapsed_seconds": round(elapsed, 6)}

    def emit(value):
        print(canonical(value), file=sys.stderr, flush=True)

    try:
        journal(args.ledger)
        ledger_valid = True
        if os.name != "posix" or sys.stdin.isatty():
            raise ValueError("Supply raw PCM through a pipe or file on Linux/Termux")
        backend, sink = open_sink(args)
        emit(packet("starting"))
        last = started - args.interval
        frame_bytes = 2 * args.channels
        while True:
            sink.check()
            if not select.select([sys.stdin.fileno()], [], [], 0.2)[0]:
                continue
            chunk = os.read(sys.stdin.fileno(), args.chunk_bytes)
            if not chunk:
                break
            received += len(chunk)
            input_hash.update(chunk)
            pending += chunk
            size = len(pending) - len(pending) % frame_bytes
            ready, pending = pending[:size], pending[size:]
            offset = 0
            while offset < len(ready):
                count = sink.write(memoryview(ready)[offset:], args.stall_timeout)
                if not count:
                    raise RuntimeError("Sink accepted zero bytes")
                sink_hash.update(ready[offset:offset + count])
                submitted += count
                offset += count
            if time.monotonic() - last >= args.interval:
                emit(packet("streaming"))
                last = time.monotonic()
        if pending:
            raise ValueError(f"Incomplete PCM frame at EOF: {len(pending)} trailing bytes")
        if args.expect_sha256 and input_hash.hexdigest() != args.expect_sha256:
            raise ValueError("Input SHA-256 differs from the expected checksum")
        status = "completed"
    except KeyboardInterrupt:
        status, error, result = "cancelled", "Interrupted by signal", 128 + stop_signal
    except (OSError, ValueError, RuntimeError) as exc:
        status, error, result = "failed", str(exc), 1
    finally:
        if sink is not None:
            try:
                sink.finish(status != "completed", args.drain_timeout if status == "completed" else 2)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                status, error, result = "failed", str(exc), 1
        receipt = {**packet(status), "input_sha256": input_hash.hexdigest(),
                   "submitted_sha256": sink_hash.hexdigest(),
                   "checksum_check": "not_requested" if not args.expect_sha256 else
                       ("matched" if input_hash.hexdigest() == args.expect_sha256 else "mismatch"),
                   "source_authenticated": False, "acoustic_playback_verified": False,
                   "sink_exit_code": sink.proc.returncode if sink and sink.proc else None,
                   "exit_code": result, "error": error}
        if sink and sink.proc:
            receipt["sink_stderr_tail"] = bytes(sink.tail).decode("utf-8", errors="replace")
        if ledger_valid:
            try:
                receipt["ledger_head"] = journal(args.ledger, receipt)
            except (OSError, ValueError) as exc:
                receipt.update(status="failed", exit_code=1, ledger_error=str(exc))
                result = 1
        try:
            emit(receipt)
        except (OSError, ValueError):
            result = 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
