#!/usr/bin/env python3
"""Local archive review with actual response headers; not a GitHub Pages setting."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
import argparse
import mimetypes

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("imports/2026-10-09/", "security/")
POLICY = "object-src 'none'; base-uri 'none'; form-action 'self'; connect-src 'self'; frame-ancestors 'none'"

class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Content-Security-Policy', POLICY)
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        path = unquote(urlsplit(self.path).path).lstrip('/') or 'catalog.md'
        if '\\' in path or '\x00' in path or '%' in path or any(part in {'.', '..'} or part.startswith('.') for part in path.split('/')):
            self.send_error(404); return
        if path != 'catalog.md' and not path.startswith(ALLOWED):
            self.send_error(404); return
        original = ROOT / path
        if any(parent.is_symlink() for parent in (original, *original.parents)):
            self.send_error(404); return
        target = original.resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            self.send_error(404); return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', (mimetypes.guess_type(path)[0] or 'application/octet-stream') + ('; charset=utf-8' if path.endswith(('.md', '.html', '.js')) else ''))
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def log_message(self, *_):
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8878)
    args = parser.parse_args()
    print(f'Local review only: http://127.0.0.1:{args.port}/')
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
