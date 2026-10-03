# HTTPDFS compatibility layer

Read-oriented filesystem interface for the OMNI-KERNEL runtime.

## Contract

- `GET /api/fs/tree` -> hierarchical manifest
- `GET /api/fs/meta?path=...` -> metadata
- `GET /api/fs/file?path=...` -> contents for allow-listed archive/runtime roots

The browser consumes generated manifests instead of unrestricted host paths. Mutating endpoints are intentionally omitted from the default design.

## Source adapters

1. Local mounted project artifacts
2. Google Drive inventory/fetch adapter
3. GitHub repository tree
4. Chat/session synchronization ledger

Each artifact should carry source, source_id, path, MIME/kind, hash when available, imported_at, and lineage.
