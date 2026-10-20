# GAIA ∞ HyperTerminal — Masterwork v5.0.0

Owner: **Azazeleous** · Repository target: `Azazeleous/OMNI-KERNEL-The-Oracle-Singularity`

## Scope

This release is a zero-CDN, single-file browser operating *surface*, **not** a native operating system. It includes:

- an encapsulated Shadow DOM terminal with keyboard commands and histories;
- a persisted local Virtual Filesystem (VFS), bounded writes, JSON import/export;
- a graph renderer derived from real VFS paths, using WebGL2 with Canvas2D fallback;
- an event ledger with SHA-256 hash-chain validation (client-tamper-evident, **not** a trusted external attestation);
- an HTML descendant ('quine') exporter that embeds the current VFS + ledger;
- an explicit loopback-only bridge health test; no arbitrary shell commands or credentials on public GitHub Pages.

## Deployment

GitHub Pages can host this `index.html` directly. Use this as the **canonical terminal entry point**, or embed it in another site with a user-activated iframe. Do **not** replace non-terminal applications (GeoCore tone generator, -z-m art surface, Next.js upstream fork) to satisfy a sitewide terminal replacement request.

For an existing terminal page, compare the file path, archive a git commit, replace only the terminal component, and retain existing application routes. Configure Pages to deploy from the repository's GitHub Actions workflow (if enabled). Validate the live URL after merging.

For local preview on desktop/Chromebook, run from the folder:

```sh
python3 -m http.server 8080 --bind 127.0.0.1
```

Visit `http://127.0.0.1:8080/`. For Android, the HTML also opens in an editor/browser; privileged functions still require an authenticated local bridge.

## ADAM evidence scope

`BROWSER_VERIFICATION.json` records static and isolated-Chromium checks. Its opaque-origin WebCrypto limitation means **full ledger writing, quine generation, real WebGL2 GPU availability, localhost health CORS integration, and GitHub Pages delivery remain unverified end-to-end**. The CLI must not claim these functions are fully production-verified until those additional checks pass on the target origin/device.

GitHub owner is explicitly Azazeleous. No changes to machackabook or other linked accounts are part of this release.