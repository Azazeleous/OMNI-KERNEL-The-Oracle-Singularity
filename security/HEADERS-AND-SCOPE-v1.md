# Public boundary hardening v1.1.0

Personal email addresses and private network addresses were removed from current imported text. The original source hash remains provenance, with previous and new published hashes recorded. Historical commits and old branches retain original material; this is not a history purge.

The browser boundary carries explicitly labelled values to bounded text sinks, rejects unsafe/private citation URLs and restricts API names to fixed same-origin paths. The spine logs and saved ledger no longer insert untrusted HTML. Provider citations use structural DOM nodes. A label is a programming convention, not an authorization token, and labels do not propagate automatically through arbitrary JavaScript.

Provider secrets are never supplied by the public interface. Historical Gemini interfaces now require a separately implemented and authenticated same-origin backend at `/api/gemini/generate`; no backend deployment is implied. Remote relay fallback and archive device WebSockets are disabled. External CDN assets remain a supply-chain dependency. Inline vendor bundles and all historical UI paths have not received comprehensive browser or data-flow verification.

The meta policy blocks plugin objects, base-tag injection, cross-origin form submission and cross-origin fetch/WebSocket requests. It does not implement `frame-ancestors`. GitHub Pages response headers were observed without a CSP framing policy or X-Frame-Options. A meta tag or `_headers` file cannot be assumed to change GitHub Pages response headers.

For a configurable hosting service or trusted reverse proxy, serve ALL HTML documents, including errors and nested routes, with these response headers:

```
Content-Security-Policy: object-src 'none'; base-uri 'none'; form-action 'self'; connect-src 'self'; frame-ancestors 'none'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

`python3 scripts/serve_public_v1.py` provides these actual headers on a loopback-only review server. It publishes only the dated import and boundary assets, not `.git`, scripts, runtime configuration or arbitrary host paths. It is not an Internet deployment. Imported browser visuals still request external CDN assets; complete script allowlisting/SRI requires a reviewed dependency/build migration.

Public DNS and delivered frontend assets are observable. Browser DevTools, source inspection and copying cannot be disabled securely by a webpage. Sensitive logic belongs on an authenticated server and private repositories. Authentication/rate limiting can restrict access to a deployed application but cannot erase copies already delivered to a client. Robots rules and obfuscation are not access controls.

The GitHub token found in another public repository must be revoked/rotated by its owner. Removing it from HEAD is insufficient. Do not use test fixture keys as operational credentials. Account MFA, Actions secrets, protected branches, secret-scanning alerts and push-protection settings remain unverified unless explicitly checked through an administrative interface.
