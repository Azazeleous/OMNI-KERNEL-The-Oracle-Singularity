"""Actual file/process/lock checks. No sound-device or acoustic proof is asserted."""
import concurrent.futures
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "runtime" / "gaia_audio_stream_v5.0.1.py"
spec = importlib.util.spec_from_file_location("gaia_audio", SCRIPT)
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class AudioChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pcm = b"".join(struct.pack("<hh", value, value) for value in
            (int(1600 * math.sin(2 * math.pi * 440 * n / 44100)) for n in range(2205)))

    def tearDown(self):
        self.tmp.cleanup()

    def command(self, output="actual.pcm", ledger="ledger.jsonl", *extra):
        return [sys.executable, str(SCRIPT), "--backend", "record", "--output",
                str(self.root / output), "--ledger", str(self.root / ledger), *extra]

    def run_cli(self, data=None, *extra):
        result = subprocess.run(self.command("actual.pcm", "ledger.jsonl", *extra),
            input=self.pcm if data is None else data, capture_output=True, timeout=5)
        self.assertEqual(result.stdout, b"")
        packets = [json.loads(line) for line in result.stderr.splitlines()]
        self.assertTrue(packets)
        return result, packets[-1]

    def test_recorded_pcm_is_exact_across_unaligned_reads(self):
        result, receipt = self.run_cli(None, "--chunk-bytes", "7",
                                     "--expect-sha256", hashlib.sha256(self.pcm).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "actual.pcm").read_bytes(), self.pcm)
        self.assertEqual(receipt["bytes_received"], len(self.pcm))
        self.assertEqual(receipt["bytes_submitted"], len(self.pcm))
        self.assertEqual(receipt["frames_submitted"], 2205)
        self.assertAlmostEqual(receipt["pcm_seconds_submitted"], 0.05)
        self.assertEqual(receipt["submitted_sha256"], hashlib.sha256(self.pcm).hexdigest())
        self.assertEqual(receipt["checksum_check"], "matched")
        self.assertFalse(receipt["source_authenticated"])
        self.assertFalse(receipt["acoustic_playback_verified"])
        self.assertEqual(audio.journal(self.root / "ledger.jsonl"), receipt["ledger_head"])

    def test_partial_frame_is_rejected_and_not_padded(self):
        result, receipt = self.run_cli(self.pcm + b"\x01\x02\x03")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(receipt["status"], "failed")
        self.assertIn("trailing bytes", receipt["error"])
        self.assertEqual((self.root / "actual.pcm").read_bytes(), self.pcm)
        self.assertEqual(receipt["bytes_received"] - receipt["bytes_submitted"], 3)

    def test_checksum_mismatch_is_failed_after_submission(self):
        result, receipt = self.run_cli(None, "--expect-sha256", "0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(receipt["checksum_check"], "mismatch")
        self.assertEqual((self.root / "actual.pcm").read_bytes(), self.pcm)

    def test_existing_recording_is_preserved(self):
        output = self.root / "actual.pcm"
        output.write_bytes(b"retain previous recording")
        result, receipt = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b"retain previous recording")
        self.assertEqual(receipt["bytes_submitted"], 0)

    def test_ledger_tampering_blocks_sink_creation(self):
        ledger = self.root / "ledger.jsonl"
        audio.journal(ledger, {"observed": 1})
        record = json.loads(ledger.read_text())
        record["payload"]["observed"] = 2
        altered = json.dumps(record) + "\n"
        ledger.write_text(altered)
        result, receipt = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("hash-chain mismatch", receipt["error"])
        self.assertFalse((self.root / "actual.pcm").exists())
        self.assertEqual(ledger.read_text(), altered)

    def test_concurrent_processes_append_one_valid_chain(self):
        def run_one(index):
            return subprocess.run(self.command(f"session-{index}.pcm"), input=self.pcm,
                                  capture_output=True, timeout=10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(run_one, range(12)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(x) for x in (self.root / "ledger.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 12)
        self.assertEqual(len({r["payload"]["session"] for r in records}), 12)
        self.assertEqual(audio.journal(self.root / "ledger.jsonl"), records[-1]["hash"])
        for index in range(12):
            self.assertEqual((self.root / f"session-{index}.pcm").read_bytes(), self.pcm)

    def test_real_held_ledger_lock_has_a_timeout(self):
        ledger = self.root / "held.jsonl"
        with ledger.open("w+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            start = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "ledger lock timeout"):
                audio.journal(ledger, lock_timeout=0.2)
            self.assertLess(time.monotonic() - start, 1)

    def test_missing_backend_reports_failure_without_consuming_input(self):
        env = dict(os.environ, PATH=str(self.root))
        result = subprocess.run([sys.executable, str(SCRIPT), "--backend", "alsa",
            "--ledger", str(self.root / "ledger.jsonl")], input=self.pcm,
            capture_output=True, env=env, timeout=5)
        receipt = json.loads(result.stderr.splitlines()[-1])
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing aplay", receipt["error"])
        self.assertEqual(receipt["bytes_received"], 0)

    def test_sigterm_is_cancelled_and_receipt_is_retained(self):
        proc = subprocess.Popen(self.command(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            starting = json.loads(proc.stderr.readline())
            self.assertEqual(starting["status"], "starting")
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=5)
            receipt = json.loads(err.splitlines()[-1])
            self.assertEqual(out, b"")
            self.assertEqual(proc.returncode, 143)
            self.assertEqual(receipt["status"], "cancelled")
            self.assertEqual(json.loads((self.root / "ledger.jsonl").read_text())["payload"]["status"], "cancelled")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_installer_source_identity_idempotence_backup_and_installed_recording(self):
        installer = SCRIPT.parents[1] / "tools/GAIA_AUDIO_STREAM_v5.0.1.sh"
        text = installer.read_text()
        embedded = text.split("<<'PY_AUDIO_V5_0_1'\n", 1)[1].split("\nPY_AUDIO_V5_0_1\n", 1)[0] + "\n"
        self.assertEqual(embedded.encode(), SCRIPT.read_bytes())
        subprocess.run(["bash", "-n", str(installer)], check=True, capture_output=True)
        ae = self.root / "ae"
        downloads = self.root / "downloads"
        env = dict(os.environ, AE=str(ae), NEXUS_AUDIO_DOWNLOADS=str(downloads))
        target = ae / "autonomous/GAIA_AUDIO_STREAM_v5.0.1.py"
        for _ in range(2):
            result = subprocess.run(["bash", str(installer)], env=env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), SCRIPT.read_bytes())
        self.assertEqual(list(target.parent.glob(target.name + ".backup.*")), [])
        altered = SCRIPT.read_bytes() + b"\n# Retained previous installation\n"
        target.write_bytes(altered)
        result = subprocess.run(["bash", str(installer)], env=env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(target.parent.glob(target.name + ".backup.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), altered)
        self.assertEqual(target.read_bytes(), SCRIPT.read_bytes())
        self.assertEqual((downloads / target.name).read_bytes(), SCRIPT.read_bytes())
        metadata = json.loads(Path(str(target) + ".meta.json").read_text())
        self.assertEqual(metadata["sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        result = subprocess.run([sys.executable, str(ae / "bin/gaia-audio"), "--backend", "record",
            "--output", str(self.root / "installed.pcm")], input=self.pcm,
            capture_output=True, env=env, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "installed.pcm").read_bytes(), self.pcm)
        self.assertTrue((ae / "logs/audio_stream_v5.0.1.jsonl").exists())

    def write_all(self, sink, data, timeout=2):
        offset, writes = 0, 0
        while offset < len(data):
            count = sink.write(memoryview(data)[offset:], timeout)
            self.assertGreater(count, 0)
            offset += count
            writes += 1
        return writes

    @unittest.skipUnless(shutil.which("tee"), "tee unavailable")
    def test_real_pipe_partial_writes_preserve_all_bytes(self):
        output = self.root / "tee.pcm"
        sink = audio.Sink(command=[shutil.which("tee"), str(output)])
        data = self.pcm * 100
        try:
            writes = self.write_all(sink, data)
            self.assertGreater(writes, 1)
            self.assertEqual(sink.finish(False, 3), 0)
            self.assertEqual(output.read_bytes(), data)
            self.assertIsNotNone(sink.proc.returncode)
        finally:
            if sink.proc.poll() is None:
                sink.finish(True, 2)

    @unittest.skipUnless(shutil.which("dd"), "dd unavailable")
    def test_real_stderr_pressure_is_drained_and_tail_is_bounded(self):
        sink = audio.Sink(command=[shutil.which("dd"), "of=/dev/stderr", "bs=4096", "status=none"])
        data = self.pcm * 100
        try:
            self.write_all(sink, data)
            self.assertEqual(sink.finish(False, 3), 0)
            self.assertEqual(len(sink.tail), 4096)
            self.assertEqual(bytes(sink.tail), data[-4096:])
        finally:
            if sink.proc.poll() is None:
                sink.finish(True, 2)

    @unittest.skipUnless(shutil.which("sleep"), "sleep unavailable")
    def test_real_blocked_pipe_times_out_and_child_is_reaped(self):
        sink = audio.Sink(command=[shutil.which("sleep"), "30"])
        start = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                self.write_all(sink, self.pcm * 100, timeout=0.2)
        finally:
            sink.finish(True, 2)
        self.assertLess(time.monotonic() - start, 3)
        self.assertIsNotNone(sink.proc.returncode)

    @unittest.skipUnless(shutil.which("sleep"), "sleep unavailable")
    def test_real_drain_timeout_reaps_child(self):
        sink = audio.Sink(command=[shutil.which("sleep"), "30"])
        with self.assertRaises(TimeoutError):
            sink.finish(False, 0.2)
        self.assertIsNotNone(sink.proc.returncode)


if __name__ == "__main__":
    unittest.main()
