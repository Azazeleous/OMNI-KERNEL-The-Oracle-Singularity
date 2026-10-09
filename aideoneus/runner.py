#!/usr/bin/env python3
"""Aideoneus Gates v1: fail-closed evidence gates; Python stdlib only.

This provides integrity evidence, not identity authentication or cryptographic signing.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys

MAX_FILE_SIZE = 5 * 1024 * 1024
VALID_PATH = re.compile(r"^[A-Za-z0-9_.@+/-]+$")
SYMBOLS = {"observe": "‽", "heal": "⚚ₙ", "form": "Φ", "clarity": "⟐", "foundation": "⬢"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or not VALID_PATH.fullmatch(relative):
        raise ValueError(f"Invalid relative path: {relative!r}")
    candidate = Path(relative)
    if candidate.is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")):
        raise ValueError(f"Path traversal: {relative}")
    location = root / candidate
    for part in [root, *[root.joinpath(*candidate.parts[:i]) for i in range(1, len(candidate.parts) + 1)]]:
        if part.is_symlink():
            raise ValueError(f"Symlink not accepted: {relative}")
    if not location.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path outside workspace: {relative}")
    return location


def read_policy(root, name):
    path = safe_path(root, name)
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or policy.get("schema") != "aideoneus.policy.v1":
        raise ValueError("Invalid policy schema")
    files = policy.get("required_files")
    if not isinstance(files, list) or not files or len(files) > 512 or any(not isinstance(x, str) for x in files):
        raise ValueError("required_files must be a nonempty string list (max 512)")
    if len(set(files)) != len(files):
        raise ValueError("Duplicate required_files")
    if not policy.get("purpose") or not isinstance(policy["purpose"], str):
        raise ValueError("A documented purpose is required")
    for f in files:
        safe_path(root, f)
    return policy


def observe(root, paths):
    readings = []
    for rel in sorted(paths):
        loc = safe_path(root, rel)
        if not loc.is_file():
            raise ValueError(f"Required regular file missing: {rel}")
        size = loc.stat().st_size
        if size <= 0 or size > MAX_FILE_SIZE:
            raise ValueError(f"File empty or over {MAX_FILE_SIZE} bytes: {rel}")
        data = loc.read_bytes()
        if len(data) != size:
            raise ValueError(f"Concurrent write detected: {rel}")
        readings.append({"path": rel, "size": size, "sha256": sha(data),
                         "kind": classify(rel)})
    return readings


def classify(path):
    if path.endswith((".py", ".sh", ".js", ".ts")):
        return "code"
    if path.endswith((".yml", ".yaml")):
        return "workflow"
    if path.endswith(".json"):
        return "policy_or_data"
    return "document"


def verify_ledger(path):
    if not path.exists():
        return {"valid": True, "entries": 0, "head": "0" * 64}
    previous = "0" * 64
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        count += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed ledger entry {count}") from exc
        if not isinstance(entry, dict) or set(entry) != {"event", "prev_hash", "entry_hash"}:
            raise ValueError(f"Wrong ledger fields at entry {count}")
        if entry["prev_hash"] != previous or not isinstance(entry["event"], dict):
            raise ValueError(f"Ledger chain mismatch at entry {count}")
        expected = sha(canonical({"event": entry["event"], "prev_hash": previous}))
        if entry["entry_hash"] != expected:
            raise ValueError(f"Ledger digest mismatch at entry {count}")
        previous = expected
    return {"valid": True, "entries": count, "head": previous}


def append_event(ledger, event):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    chain = verify_ledger(ledger)
    base = {"event": event, "prev_hash": chain["head"]}
    entry = {**base, "entry_hash": sha(canonical(base))}
    with ledger.open("a", encoding="utf-8") as target:
        target.write(canonical(entry).decode("utf-8") + "\n")
        target.flush()
        os.fsync(target.fileno())
    return entry["entry_hash"]


def run(root, policy_name, output):
    output.mkdir(parents=True, exist_ok=True)
    ledger = output / "ledger.jsonl"
    report = output / "report.json"
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    stages = []
    outcome = "blocked"
    fingerprints = []
    reason = None
    policy_digest = None
    try:
        # ⬢ Foundation: verify existing ledger before adding anything.
        verify_ledger(ledger)
        # ‽ Observe: policy and physical files must exist and be readable.
        policy = read_policy(root, policy_name)
        policy_digest = sha(canonical(policy))
        stages.append({"gate": "discover", "status": "pass"})
        first = observe(root, policy["required_files"])
        stages.append({"gate": "observe", "operator": SYMBOLS["observe"], "status": "pass", "count": len(first)})
        # ⚚ Healing: validation and explicit fail-close; never silently mutate input.
        stages.append({"gate": "normalize_classify", "operator": SYMBOLS["heal"], "status": "pass"})
        # Φ Form: reproducible ordering / deterministic fingerprint.
        fingerprints = first
        aggregate = sha(canonical(fingerprints))
        stages.append({"gate": "fingerprint", "operator": SYMBOLS["form"], "status": "pass", "sha256": aggregate})
        # ⟐ Clarity: re-read files immediately before promotion, detect changes.
        second = observe(root, policy["required_files"])
        if second != first:
            raise ValueError("Reverification mismatch: inputs changed during gate run")
        stages.append({"gate": "reverify", "operator": SYMBOLS["clarity"], "status": "pass"})
        stages.append({"gate": "remedy", "status": "not_required", "automatic_changes": False})
        outcome = "promoted"
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        reason = f"{type(exc).__name__}: {str(exc)[:400]}"
        stages.append({"gate": "block", "status": "fail", "reason": reason})
    result = {"schema": "aideoneus.report.v1", "timestamp_utc": start,
              "policy_sha256": policy_digest, "status": outcome,
              "files": fingerprints, "stages": stages,
              "reason": reason, "limits": "SHA-256 chain is not a signature; external anchoring is required for tamper-evident history."}
    event = {"status": outcome, "timestamp_utc": start, "report_sha256": sha(canonical(result))}
    # If the ledger was corrupted, refuse to append; never rewrite evidence.
    try:
        result["ledger_head"] = append_event(ledger, event)
    except (ValueError, OSError) as exc:
        result["status"] = "blocked"
        result["reason"] = "Ledger integrity/write failure: " + str(exc)[:400]
        result["ledger_head"] = None
    report.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"status": result["status"], "report": str(report),
                      "ledger": str(ledger), "reason": result["reason"]}, ensure_ascii=False))
    return 0 if result["status"] == "promoted" else 1


def main():
    parser = argparse.ArgumentParser(description="Aideoneus evidence-first gate runner")
    subs = parser.add_subparsers(dest="command", required=True)
    gate = subs.add_parser("run")
    gate.add_argument("--root", default=".")
    gate.add_argument("--policy", default="aideoneus/policy.json")
    gate.add_argument("--output", default=".aideoneus")
    check = subs.add_parser("verify-ledger")
    check.add_argument("--ledger", default=".aideoneus/ledger.jsonl")
    args = parser.parse_args()
    if args.command == "verify-ledger":
        try:
            print(json.dumps(verify_ledger(Path(args.ledger)), sort_keys=True))
            return 0
        except (ValueError, OSError) as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 1
    return run(Path(args.root).resolve(), args.policy, Path(args.output).resolve())


if __name__ == "__main__":
    sys.exit(main())
