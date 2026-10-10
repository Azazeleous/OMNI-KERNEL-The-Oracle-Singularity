"""Signal fixtures and real OS pipes/codec/locks; no acoustic hardware proof."""
from array import array
import cmath
import concurrent.futures
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "runtime/gaia_audio_feedback_v5.0.2.py"
module_spec = importlib.util.spec_from_file_location("gaia_feedback", SCRIPT)
feedback = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(feedback)


def pcm(values):
    result = array("h", values)
    if sys.byteorder != "little":
        result.byteswap()
    return result.tobytes()


def samples(raw):
    result = array("h")
    result.frombytes(raw)
    if sys.byteorder != "little":
        result.byteswap()
    return result


class FeedbackChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = feedback.new_spec()
        cls.spec.update(nonce="a" * 32, order=[0, 3, 6, 2, 5, 1, 7, 4, 2, 6, 1, 5])
        cls.probe = feedback.probe_pcm(cls.spec)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, data=None, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=data,
                              capture_output=True, timeout=12, env=env)

    def test_fft_matches_independent_discrete_fourier_sum(self):
        values = [complex(math.sin(i * 0.71), math.cos(i * 0.29)) for i in range(32)]
        actual = feedback.fft(values)
        expected = [sum(x * cmath.exp(-2j * math.pi * k * n / len(values))
                        for n, x in enumerate(values)) for k in range(len(values))]
        self.assertLess(max(abs(a - b) for a, b in zip(actual, expected)), 1e-10)
        for length in (0, 1, 3, 15):
            with self.assertRaises(ValueError):
                feedback.fft([0] * length)

    def test_delayed_attenuated_probe_with_noise_and_dc_is_detected(self):
        rng = random.Random(12345)
        delayed = [0] * round(0.416 * feedback.RATE) + list(samples(self.probe)) + [0] * 4800
        raw = pcm(round(0.25 * x + 400 + rng.gauss(0, 6)) for x in delayed)
        result = feedback.analyze(raw, self.spec)
        self.assertTrue(result["signal_detected"])
        self.assertGreaterEqual(result["matched_steps"], 11)
        self.assertGreaterEqual(result["gap_drops"], 10)
        self.assertAlmostEqual(result["alignment_seconds"], 0.416, delta=0.064)
        self.assertFalse(result["acoustic_playback_verified"])

    def test_silence_static_tone_and_broadband_noise_are_not_detected(self):
        rng = random.Random(100)
        length = len(self.probe) // 2
        frequency = feedback.BINS[0] * feedback.RATE / feedback.NFFT
        variants = [b"\0" * len(self.probe),
                    pcm(round(1000 * math.sin(2 * math.pi * frequency * n / feedback.RATE)) for n in range(length)),
                    pcm(round(rng.gauss(0, 200)) for _ in range(length))]
        for raw in variants:
            with self.subTest(sha=feedback.sha(raw)):
                self.assertFalse(feedback.analyze(raw, self.spec)["signal_detected"])

    def test_wrong_frequency_order_does_not_match_a_fresh_challenge(self):
        other = dict(self.spec, nonce="b" * 32, order=[(x + 1) % 8 for x in self.spec["order"]])
        self.assertFalse(feedback.analyze(feedback.probe_pcm(other), self.spec)["signal_detected"])

    def test_continuous_tones_without_pauses_fail_cadence_check(self):
        values = list(samples(self.probe))
        for step, index in enumerate(self.spec["order"]):
            start = round((self.spec["lead"] + step * 0.32 + 0.2) * feedback.RATE)
            frequency = feedback.BINS[index] * feedback.RATE / feedback.NFFT
            for k in range(round(0.12 * feedback.RATE)):
                values[start + k] = round(983 * math.sin(2 * math.pi * frequency * k / feedback.RATE))
        result = feedback.analyze(pcm(values), self.spec, max_lag=0)
        self.assertFalse(result["signal_detected"])
        self.assertLess(result["gap_drops"], 10)

    def test_clipped_signal_is_rejected_even_when_tones_match(self):
        values = list(samples(self.probe))
        values[:round(0.1 * feedback.RATE)] = [32767] * round(0.1 * feedback.RATE)
        result = feedback.analyze(pcm(values), self.spec, max_lag=0)
        self.assertGreater(result["clipping_fraction"], 0.005)
        self.assertFalse(result["signal_detected"])

    def test_incomplete_oversized_and_short_pcm_are_rejected(self):
        for raw in (self.probe + b"\0", b"\0" * (feedback.MAX_BYTES + 2), self.probe[:1000]):
            with self.assertRaises(ValueError):
                feedback.analyze(raw, self.spec)
        for lag in (-0.1, 3.1, float("nan")):
            with self.assertRaises(ValueError):
                feedback.analyze(self.probe, self.spec, lag)

    def test_invalid_amplitude_and_specs_are_rejected(self):
        for amplitude in (0, 0.5, float("nan"), True):
            with self.assertRaises(ValueError):
                feedback.validate_spec(dict(self.spec, amplitude=amplitude))
        for changes in ({"nonce": "bad"}, {"rate": 44100}, {"order": [0] * 12}, {"gap": 0}):
            with self.assertRaises(ValueError):
                feedback.validate_spec(dict(self.spec, **changes))

    def test_actual_emit_to_analyze_pipe_is_signal_evidence_only(self):
        path = self.root / "probe.json"
        created = self.cli("create", "--spec", str(path))
        self.assertEqual(created.returncode, 0, created.stderr)
        previous = path.read_bytes()
        self.assertEqual(self.cli("create", "--spec", str(path)).returncode, 1)
        self.assertEqual(path.read_bytes(), previous)
        emit = subprocess.Popen([sys.executable, str(SCRIPT), "emit", "--spec", str(path)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            result = subprocess.run([sys.executable, str(SCRIPT), "analyze", "--spec", str(path)],
                                    stdin=emit.stdout, capture_output=True, timeout=12)
            emit.stdout.close()
            _, err = emit.communicate(timeout=3)
            self.assertEqual(emit.returncode, 0, err)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertTrue(receipt["signal_detected"])
            self.assertFalse(receipt["acoustic_playback_verified"])
        finally:
            if emit.poll() is None:
                emit.kill()
                emit.communicate()

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg unavailable")
    def test_actual_aac_encode_decode_pipe_preserves_detectable_sequence(self):
        encoded = self.root / "probe.m4a"
        feedback.command([shutil.which("ffmpeg"), "-v", "error", "-f", "s16le", "-ar", "16000",
                          "-ac", "1", "-i", "pipe:0", "-c:a", "aac", "-b:a", "48k", str(encoded)],
                         data=self.probe)
        decoded = feedback.command([shutil.which("ffmpeg"), "-v", "error", "-i", str(encoded),
                                    "-f", "s16le", "-ar", "16000", "-ac", "1", "pipe:1"])
        result = feedback.analyze(decoded, self.spec)
        self.assertTrue(result["signal_detected"])
        self.assertFalse(result["acoustic_playback_verified"])

    def test_source_metadata_filter_rejects_monitors_and_virtual_sources(self):
        hardware = {"name": "alsa_input.usb-microphone", "monitor_of_sink": 4294967295,
                    "properties": {"device.api": "alsa"}}
        self.assertTrue(feedback.physical_pulse_source(hardware))
        for changes in ({"name": "alsa_output.speaker.monitor"}, {"monitor_of_sink": 0},
                        {"name": "null.loopback", "monitor_of_sink": None}, {"properties": []}):
            self.assertFalse(feedback.physical_pulse_source(dict(hardware, **changes)))
        self.assertFalse(feedback.physical_pulse_source({"name": "alsa_input.unobserved"}))
        self.assertFalse(feedback.physical_pulse_source(None))

    def test_real_capture_pipe_drains_stderr_without_losing_pcm(self):
        program = "import os; os.write(2,b'd'*131072); os.write(1,b'x'*8192)"
        capture = feedback.Capture([sys.executable, "-c", program], 3)
        self.assertTrue(capture.ready.wait(2))
        self.assertEqual(capture.finish(), b"x" * 8192)
        self.assertEqual(bytes(capture.tail), b"d" * 4096)
        self.assertIsNotNone(capture.proc.returncode)

    def test_real_capture_failure_is_not_masked_by_stop_request(self):
        program = "import os,sys; os.write(1,b'x'*2048); sys.stderr.write('capture failed'); sys.exit(7)"
        capture = feedback.Capture([sys.executable, "-c", program], 3)
        capture.worker.join(3)
        self.assertEqual(capture.proc.returncode, 7)
        with self.assertRaisesRegex(RuntimeError, "capture failed"):
            capture.finish()

    def test_real_capture_byte_limit_reaps_source(self):
        capture = feedback.Capture([sys.executable, "-c", "import os; os.write(1,b'x'*700000)"], 3)
        capture.worker.join(3)
        with self.assertRaisesRegex(RuntimeError, "byte limit"):
            capture.finish()
        self.assertIsNotNone(capture.proc.returncode)

    def test_real_capture_deadline_terminates_and_reaps_idle_source(self):
        started = time.monotonic()
        capture = feedback.Capture([sys.executable, "-c", "import time; time.sleep(10)"], 0.2)
        capture.worker.join(3)
        self.assertEqual(capture.finish(), b"")
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(capture.proc.returncode, -signal.SIGTERM)

    def test_real_command_timeout_reaps_child(self):
        pidfile = self.root / "pid"
        program = "import os,time,pathlib; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(10)" % str(pidfile)
        with self.assertRaises(subprocess.TimeoutExpired):
            feedback.command([sys.executable, "-c", program], timeout=0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)

    def test_ledger_tampering_blocks_before_backend_or_capture(self):
        ledger = self.root / "audio_feedback_v5.0.2.jsonl"
        feedback.journal(ledger, {"signal_detected": False})
        record = json.loads(ledger.read_text())
        record["payload"]["signal_detected"] = True
        altered = json.dumps(record) + "\n"
        ledger.write_text(altered)
        result = self.cli("check", "--physical-mic", "--backend", "termux", "--state-dir", str(self.root),
                          env=dict(os.environ, PATH=str(self.root)))
        self.assertEqual(result.returncode, 1)
        self.assertIn("integrity verification", result.stderr.decode())
        self.assertEqual(ledger.read_text(), altered)
        self.assertEqual(list(self.root.glob("session-*")), [])

    def test_concurrent_processes_append_one_valid_feedback_chain(self):
        ledger = self.root / "chain.jsonl"
        program = ("import importlib.util,pathlib,sys; s=importlib.util.spec_from_file_location('f',sys.argv[1]); "
                   "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                   "m.journal(pathlib.Path(sys.argv[2]),{'id':sys.argv[3],'acoustic_playback_verified':False})")
        def append(index):
            return subprocess.run([sys.executable, "-c", program, str(SCRIPT), str(ledger), str(index)],
                                  capture_output=True, timeout=8)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(append, range(8)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in ledger.read_text().splitlines()]
        self.assertEqual(len(records), 8)
        self.assertEqual(len({r["payload"]["id"] for r in records}), 8)
        self.assertEqual(feedback.journal(ledger), records[-1]["hash"])

    def test_real_ledger_lock_times_out(self):
        ledger = self.root / "locked.jsonl"
        with ledger.open("w+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            with self.assertRaisesRegex(TimeoutError, "lock timeout"):
                feedback.journal(ledger, lock_timeout=0.1)

    def test_missing_backend_and_missing_physical_declaration_report_false(self):
        for extra in ([], ["--physical-mic"]):
            result = self.cli("check", "--backend", "termux", "--state-dir", str(self.root), *extra,
                              env=dict(os.environ, PATH=str(self.root)))
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stderr)["acoustic_playback_verified"])
            self.assertEqual(list(self.root.glob("session-*")), [])

    def test_sigterm_interrupts_waiting_analyzer_and_reports_cancelled(self):
        path = self.root / "probe.json"
        path.write_text(json.dumps(self.spec))
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "analyze", "--spec", str(path)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            # Main has parsed arguments and is waiting for EOF; no hardware opened.
            time.sleep(0.2)
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=3)
            self.assertEqual(out, b"")
            self.assertEqual(proc.returncode, 143)
            self.assertEqual(json.loads(err)["status"], "cancelled")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_installer_source_identity_backup_and_installed_analyzer(self):
        installer = SCRIPT.parents[1] / "tools/GAIA_AUDIO_FEEDBACK_v5.0.2.sh"
        text = installer.read_text()
        embedded = text.split("<<'PY_FEEDBACK_V5_0_2'\n", 1)[1].split("\nPY_FEEDBACK_V5_0_2\n", 1)[0] + "\n"
        self.assertEqual(embedded.encode(), SCRIPT.read_bytes())
        subprocess.run(["bash", "-n", str(installer)], check=True, capture_output=True)
        ae, downloads = self.root / "ae", self.root / "downloads"
        env = dict(os.environ, AE=str(ae), NEXUS_AUDIO_DOWNLOADS=str(downloads))
        target = ae / "autonomous/GAIA_AUDIO_FEEDBACK_v5.0.2.py"
        for _ in range(2):
            result = subprocess.run(["bash", str(installer)], env=env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), SCRIPT.read_bytes())
        altered = SCRIPT.read_bytes() + b"\n# Previous local edit retained\n"
        target.write_bytes(altered)
        result = subprocess.run(["bash", str(installer)], env=env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(target.parent.glob(target.name + ".backup.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), altered)
        self.assertEqual((downloads / target.name).read_bytes(), SCRIPT.read_bytes())
        metadata = json.loads(Path(str(target) + ".meta.json").read_text())
        self.assertEqual(metadata["sha256"], feedback.sha(SCRIPT.read_bytes()))
        path = self.root / "probe.json"
        path.write_text(json.dumps(self.spec))
        result = subprocess.run([sys.executable, str(ae / "bin/gaia-speaker-check"), "analyze", "--spec", str(path)],
                                input=self.probe, capture_output=True, timeout=12, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["acoustic_playback_verified"])
        # Exercise installer --check forwarding with an invalid route before any audio can open.
        result = subprocess.run(["bash", str(installer), "--check", "--backend", "termux",
                                 "--source", "invalid", "--state-dir", str(self.root / "state")],
                                capture_output=True, timeout=5, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("--source applies to Linux capture only", result.stderr.decode())
        self.assertFalse(json.loads(result.stderr)["acoustic_playback_verified"])


if __name__ == "__main__":
    unittest.main()
