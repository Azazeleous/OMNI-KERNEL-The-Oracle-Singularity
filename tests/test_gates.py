import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'aideoneus'))
from runner import append_event, observe, read_policy, run, safe_path, verify_ledger


class GatesTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        (self.root / 'aideoneus').mkdir()
        (self.root / 'README.md').write_text('real project evidence\n', encoding='utf-8')
        (self.root / 'aideoneus/policy.json').write_text(json.dumps({
            'schema': 'aideoneus.policy.v1',
            'purpose': 'integrity', 'required_files': ['README.md']}), encoding='utf-8')

    def tearDown(self):
        self.t.cleanup()

    def test_pass_and_verify_real_ledger(self):
        destination = self.root / 'evidence'
        self.assertEqual(run(self.root, 'aideoneus/policy.json', destination), 0)
        self.assertEqual(verify_ledger(destination / 'ledger.jsonl')['entries'], 1)
        report = json.loads((destination / 'report.json').read_text())
        self.assertEqual(report['status'], 'promoted')
        self.assertEqual(len(report['files']), 1)

    def test_missing_file_blocks(self):
        (self.root / 'README.md').unlink()
        destination = self.root / 'evidence'
        self.assertEqual(run(self.root, 'aideoneus/policy.json', destination), 1)
        self.assertEqual(json.loads((destination / 'report.json').read_text())['status'], 'blocked')

    def test_traversal_rejected(self):
        for name in ('../secrets', '/tmp/key', 'a/../../b', './README.md'):
            with self.assertRaises(ValueError):
                safe_path(self.root, name)

    def test_tamper_detection(self):
        ledger = self.root / 'ledger.jsonl'
        append_event(ledger, {'message': 'created'})
        append_event(ledger, {'message': 'second'})
        self.assertEqual(verify_ledger(ledger)['entries'], 2)
        contents = ledger.read_text().replace('second', 'altered')
        ledger.write_text(contents)
        with self.assertRaises(ValueError):
            verify_ledger(ledger)

    def test_symlink_rejected(self):
        (self.root / 'link').symlink_to(self.root / 'README.md')
        with self.assertRaises(ValueError):
            observe(self.root, ['link'])

    def test_invalid_schema_blocks(self):
        (self.root / 'aideoneus/policy.json').write_text('{"schema":"wrong", "required_files":["README.md"]}')
        with self.assertRaises(ValueError):
            read_policy(self.root, 'aideoneus/policy.json')


if __name__ == '__main__':
    unittest.main()
