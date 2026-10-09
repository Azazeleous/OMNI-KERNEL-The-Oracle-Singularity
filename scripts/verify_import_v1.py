from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parents[1]
m = json.loads((root / "imports/2026-10-09/manifest.json").read_text())
for source in m["sources"]:
    if source["destination"]:
        path = root / source["destination"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["published_sha256"], source["destination"]
print("Verified 24 imported source checksums; runtime execution remains unverified.")
