#!/usr/bin/env bash
# Professional Landing Pages v5.0.0 — MIT licensed; immutable source, verified bytes.
set -euo pipefail
command -v python3 >/dev/null || { echo 'Python 3.11+ is required.' >&2; exit 1; }
python3 - "${BASH_SOURCE[0]}" <<'INSTALL_PY'
import hashlib, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11+ is required.')
VERSION = '5.0.0'
SOURCE_COMMIT = 'undefined'
BASE = 'https://raw.githubusercontent.com/Azazeleous/OMNI-KERNEL-The-Oracle-Singularity/' + SOURCE_COMMIT + '/templates/aidesigner-pages-v5.0.0/'
FILES = {
  ".github/workflows/pages.yml": "225d3c4f5fa5a9c11f38fc815c4c430f8a472b853c92faa09d0a2f5efd2d1327",
  ".gitignore": "b6ece89ff285670694e690c3d2b5673f8867f72e031b86f1c3ac5504171f3c78",
  "LICENSE": "4f7f2d823d9fabf0fa77330755c340ddf2d1daca78dd4bbb7a3cccef0217b4e5",
  "README.md": "0bb3f23e7f1535e0e959b1b277efcfeb233d77690f963a5e58d132a253ba8077",
  "VALIDATION.md": "688c366ac9bae1a2affac1bc133759aed4039e2b7cf6f20b7a60c790c6debc3e",
  "action-pins.json": "77651ec218d434e0c0b9767b7c2ab2c1f301789657caf816d16caeb85fe752d8",
  "integration/landing-page-pages.yml": "ed17fb3ad252d7954cf23d68689f518485fa57d5d7fce2ebd1c6ded1d85ca34f",
  "integration/landing-page-quality.yml": "19e8a2b65e1be466b400007fd68d5f0e9a2a295ab25fb214774d395e076d28f6",
  "package-lock.json": "f909225a37d4aa852b8fa87e1571c63c77f99552e29e1a0e39924495ed66316f",
  "package.json": "e660061fb434e03a4de4ff7e188197d1a7b3b5ba7a6b19c7a1e354b9feacc306",
  "prompts/landing-brief.md": "55341ed8bc2d1b92b395d4b03a16cd6027d3cfb6c40714c9176acaf102d2b85b",
  "site/assets/icon.svg": "eb6b191c4fb4a7940ba83323ced2914bcef5a78da8b6d5e34d1fa0ffce9781b8",
  "site/assets/site.css": "aabd8d124f58d92a8fb1f998f57f3f884ec746f6ec12806bc4b0012d02c8fec4",
  "site/assets/site.js": "2ae566a0ea2dfc8217f7bedd5fef0a99d3ff1fd3f6e5e845fb8bf9450d3a0a66",
  "site/index.html": "14112266074ca6a0318e8c150e1244bce3f18dc0d8f6691bed0b52360a3679b9",
  "tools/browser-qa.mjs": "79878e5e2ca4c690851d50e13e92c31e1bd3653ccaed64389bb314ee9d0c7f53",
  "tools/build.py": "3c9ccbb1d54b79818b921677e39fb143e069793dec87936be0cd95f5137ffef4",
  "tools/check.py": "e5297f8ad5c34fa4967c925211de10d0d585a43002f9af8b73a85460cc929f26",
  "verification/browser-ci.json": "50b20ee36e9576fccbce63126fa9c7565f682ba4b895d6da06f826168463cbc9"
}
bundle = Path(sys.argv[1]).resolve().parent
local_bundle = (bundle / 'site/index.html').is_file() and (bundle / 'package.json').is_file()
target = Path(os.environ.get('GAIA_LANDING_TARGET', str(Path.home() / 'landing-pages-v5.0.0'))).expanduser().absolute()
if os.path.lexists(target):
    raise SystemExit('Destination already exists; choose a new GAIA_LANDING_TARGET.')
target.parent.mkdir(parents=True, exist_ok=True)
staging = Path(tempfile.mkdtemp(prefix='.landing-install-', dir=target.parent))
try:
    for relative, expected in FILES.items():
        if local_bundle:
            item = bundle / relative
            if item.is_symlink():
                raise ValueError('Symlink rejected in source bundle: ' + relative)
            data = item.read_bytes()
        else:
            with urlopen(BASE + relative, timeout=30) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('Oversized source file: ' + relative)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('SHA-256 mismatch: ' + relative)
        out = staging / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    for command in [['tools/build.py'], ['tools/check.py', 'dist']]:
        subprocess.run([sys.executable, *command], cwd=staging, check=True)
    record = {'time': datetime.now(timezone.utc).isoformat(), 'version': VERSION,
              'source_commit': SOURCE_COMMIT, 'verified_source_files': len(FILES),
              'static_checks': 'passed', 'browser_checks_executed_here': False}
    (staging / '.evidence/install.json').write_text(json.dumps(record, indent=2) + '\n')
    if os.path.lexists(target):
        raise ValueError('Destination appeared during installation; refusing overwrite.')
    staging.rename(target)
except Exception as exc:
    if staging.exists():
        shutil.rmtree(staging)
    raise SystemExit('Installation stopped: ' + str(exc))
print('Installed verified v' + VERSION + ': ' + str(target))
print('Static checks passed. Browser QA: run the README commands or use GitHub CI.')
print('Pages deployment remains the documented manual release step.')
INSTALL_PY
