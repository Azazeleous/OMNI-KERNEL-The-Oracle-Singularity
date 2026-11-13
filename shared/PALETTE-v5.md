# Nexus Global Palette v5.0.0

Canonical identifiers: GOLD #ffcc00; SPECTRUM #9932cc; CYAN #00e5ff; GREEN #34d399; RED #f87171; GRAY #94a3b8. RESET/BOLD/DIM are terminal formatting.

Browser: load shared/nexus-palette-v5.0.0.cjs with a normal script src (not a module). Use data-nexus-color="GOLD", data-nexus-gradient, and data-nexus-crystal attributes. CSS uses --nexus-gold, --nexus-spectrum, --nexus-cyan, --nexus-green, --nexus-red, --nexus-gray, --nexus-current, --nexus-gradient, --nexus-phase. Canvas/WebGL should consume NexusPalette.color(NexusPalette.phase()) or listen for nexus:phase. Static semantic colors use NexusPalette.HEX.RED, etc.

Timing: elapsed milliseconds since 2026-01-01 UTC multiplied by 0.0007 rad/ms. The four decorative anchors occupy 0°,90°,180°,270°. 360° returns to GOLD. RED and GRAY preserve fixed semantic roles. This is the existing clock's stated timing rate with a shared epoch, not a physics simulation. Device clocks must be synchronized. Reduced-motion preferences freeze decorative phase.

Node terminal: require the .cjs file and use ANSI.GOLD etc.

CLI from repository root:

```bash
node shared/nexus-palette-v5.0.0.cjs install .
node shared/nexus-palette-v5.0.0.cjs check .
node shared/nexus-palette-v5.0.0.cjs watch .
```

Install embeds the runtime in HTML with backups; repeat installs are skipped. Watch reports identifier drift and canonical literals every two seconds when files change. It does not run remotely until started, rewrite arbitrary colors, or publish files. Vendor, generated dist, original project_sources, .git, node_modules, symlinks and files over 2MB are excluded from checking. Check validates explicit data-nexus-color identifiers; literal reports are migration guidance, not failures.

Scope: shared infrastructure and a self-contained live demo. Existing render loops and all repositories have not been migrated. No private source archives, keys or disk images are published.
