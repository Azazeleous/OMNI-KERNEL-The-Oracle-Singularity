#!/usr/bin/env python3
"""Bounded text credential checks. Reports locations, never credential contents."""
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'provider-token': re.compile(r'AIza[\w-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{20,}'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----'),
    'credential-literal': re.compile(r'''(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|secret_key)\s*[:=]\s*["']([^"'\r\n]{16,})["']''', re.I),
}
findings = []
skipped = []

def scan(name, data):
    if b'\x00' in data[:4096]:
        skipped.append(name); return
    text = data.decode('utf-8', errors='replace')
    for rule, pattern in RULES.items():
        for match in pattern.finditer(text):
            if rule == 'credential-literal':
                value = match.group(1)
                if not re.search(r'[0-9]', value) or re.search(r'example|placeholder|your[_ -]|changeme|dummy|test|process\.env|os\.environ|\$\{|secrets\.|inputs\.|getenv', value, re.I):
                    continue
            findings.append((name, rule, text.count('\n', 0, match.start()) + 1))

for path in sorted(ROOT.rglob('*')):
    if not path.is_file() or '.git' in path.parts or path.is_symlink():
        continue
    name = str(path.relative_to(ROOT))
    if path.stat().st_size > 8_000_000:
        skipped.append(name); continue
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if not member.is_dir() and member.file_size < 3_000_000:
                    scan(name + '!' + member.filename, archive.read(member))
        continue
    if path.suffix.lower() in {'.pdf', '.png', '.jpg', '.gif', '.woff', '.woff2', '.pyc'}:
        skipped.append(name); continue
    scan(name, path.read_bytes())
for name, rule, line in findings:
    print(f'{name}:{line}: {rule} — content redacted')
print(f'{len(findings)} credential matches; {len(skipped)} binary/large files not covered. History and account settings require separate review.')
sys.exit(bool(findings))
