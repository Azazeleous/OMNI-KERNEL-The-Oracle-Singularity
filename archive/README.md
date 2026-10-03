# OMNI-KERNEL Archive

Canonical private integration archive for Azazeleous.

## Structure

- `archive/chats/` — explicitly synchronized session/iteration records
- `archive/html/` — source and normalized HTML artifacts
- `archive/code/` — extracted reusable code
- `archive/manifests/` — inventories, schemas, hashes, provenance
- `archive/lineage/` — source → derived relationships
- `archive/ledger/` — append-oriented synchronization records
- `archive/tdoc/` — TDOC / HELEL protocol material
- `runtime/` — runnable consolidated interfaces
- `runtime/httpdfs/` — read-oriented filesystem/Drive manifest layer

## Sync boundary

This repository stores content explicitly made available through the current session, uploaded artifacts, connected-source retrievals, and GitHub synchronization. It does not silently intercept future chats or expose arbitrary filesystem writes from a browser.
