# Nexus / GAIA source import v1.0.0

24 of 25 supplied sources are organized here. Original variant names are retained. The home backup is withheld from public publication pending private content review. Collection time is not authorship time.

- `docs/`: architecture protocol and three reference PDFs.
- `interfaces/`: historical browser interfaces and variants.
- `runtime/`: supplied JavaScript, ZIP, and safely extracted Kotlin/Gradle project.
- `manifest.json`: original and published SHA-256, destinations, provenance, exclusions.

## Evidence and blocked gates

Imported source is archival and unverified. Existing mock, simulation, success claims and architecture aspirations inside source files are historical source text, not production evidence. No device access, API connectivity, encryption, signing, firmware operation or production readiness is established by this import.

Server.js is missing package.json, prime-reallocator, chrome-config.json, router and adapters/ws-adapter. Its dependency installation runs after require calls and its browser fallback is simulated. Do not launch this historical file as a service. Weaviate-Transform.js probes schema but does not upsert objects. Its declared dependencies are unavailable.

Browser sources rely on external CDNs, user-provided API credentials, and localhost or remote services. Do not enter secrets on public Pages. Private NotebookLM identifiers were removed from source 19. No endpoint was contacted and no source script was executed during import. Enclave protocol remains a design document; implementation and platform support are not verified.

ADAM: DISCOVER / OBSERVE / CLASSIFY / FINGERPRINT have static import evidence; live VERIFY / APPLY_REMEDY / REVERIFY and runtime promotion remain blocked. Hashes confirm exact content against this stored manifest; they do not establish authorship or immutable storage.

## Local review (Linux / Crostini / Termux with git and Python 3)

```bash
git clone https://github.com/Azazeleous/OMNI-KERNEL-The-Oracle-Singularity.git OMNI-KERNEL-review && cd OMNI-KERNEL-review && python3 scripts/verify_import_v1.py
```

This command creates a separate checkout, installs no dependencies and starts no imported applications. Rollback: remove that separate checkout after retaining needed work.
