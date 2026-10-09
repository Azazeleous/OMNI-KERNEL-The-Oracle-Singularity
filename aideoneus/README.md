# OMNI-KERNEL — Aideoneus Gates v1.0

Executable Python 3 standard-library gate runner plus a reusable GitHub composite action. It maps the Linea Nigra operators into verifiable checks without treating symbolic keys, labels or payload IDs as authorization.

| Symbol | Implemented operation |
| --- | --- |
| ‽ | Discover policy, observe required files |
| ⚚ₙ | Normalize/classify; fail closed on invalid input, no automatic edits |
| Φ | Deterministic SHA-256 manifest and aggregate fingerprint |
| ⟐ | Re-read and compare content before promotion |
| ⬢ | Append integrity-linked JSONL evidence event |

## One-command execution

From the repository root:

```bash
python3 -m unittest discover -s tests -v && python3 aideoneus/runner.py run --root . --policy aideoneus/policy.json --output .aideoneus && python3 aideoneus/runner.py verify-ledger --ledger .aideoneus/ledger.jsonl
```

## GitHub integration

The pull-request and push workflow is .github/workflows/aideoneus-gates.yml. It runs all unit tests, executes the local action and uploads receipt artifacts with a 30-day retention. The composite action is .github/actions/aideoneus-gates/action.yml. It requires checkout and Python 3.9+ and operates with GitHub read-only permissions. The policy is aideoneus/policy.json.

## Evidence and security

This is real filesystem verification, not a fake success response. Missing files, malformed policy, path traversal, symlink paths, oversized files and ledger corruption block promotion. Inputs are read twice. Automatic remediation, deployments, cross-device control, and access grants are explicitly not implemented.

The append-only JSONL format contains SHA-256 hashes, not digital signatures. A malicious party with filesystem write permissions can replace a ledger and recompute hashes; external signature/anchoring and durable access control are required for stronger integrity guarantees. GitHub Action run artifacts are not durable canonical storage. Do not place secret keys, tokens, private Enclave locations or identifying device metadata in any published policy.
