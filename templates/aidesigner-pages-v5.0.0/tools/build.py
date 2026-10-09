#!/usr/bin/env python3
"""Build an allowlisted static artifact; never copy repository archives."""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE, OUTPUT = ROOT / 'site', ROOT / 'dist'
ALLOWED = {'.html', '.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff2'}

def build():
    source_files = sorted(p for p in SITE.rglob('*') if p.is_file())
    if not (SITE / 'index.html').is_file():
        raise ValueError('site/index.html is required')
    for p in SITE.rglob('*'):
        if p.is_symlink():
            raise ValueError('Symlinks cannot enter the Pages artifact')
    for p in source_files:
        if p.suffix.lower() not in ALLOWED or p.stat().st_nlink > 1 or any(x.startswith('.') for x in p.relative_to(SITE).parts):
            raise ValueError('Disallowed site file: ' + str(p.relative_to(SITE)))
    site_url = os.getenv('SITE_URL', '').strip()
    if site_url:
        u = urlsplit(site_url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError('SITE_URL must be a clean HTTPS site URL, including the project subpath')
        site_url = site_url.rstrip('/') + '/'
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SITE, OUTPUT)
    (OUTPUT / '.nojekyll').write_text('', encoding='utf-8')
    if site_url:
        html = (OUTPUT / 'index.html').read_text(encoding='utf-8')
        html = html.replace('</head>', '<link rel="canonical" href="' + escape(site_url, quote=True) + '">\n</head>')
        (OUTPUT / 'index.html').write_text(html, encoding='utf-8')
        (OUTPUT / 'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: ' + site_url + 'sitemap.xml\n', encoding='utf-8')
        (OUTPUT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + escape(site_url) + '</loc></url></urlset>\n', encoding='utf-8')
    evidence = ROOT / '.evidence'
    evidence.mkdir(exist_ok=True)
    fingerprints = {str(p.relative_to(OUTPUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUTPUT.rglob('*')) if p.is_file()}
    (evidence / 'build.json').write_text(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'version':'5.0.0','files':fingerprints},indent=2)+'\n',encoding='utf-8')
    with (evidence / 'events.jsonl').open('a', encoding='utf-8') as ledger:
        ledger.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'gate':'FINGERPRINT','event':'static_artifact_built','file_count':len(fingerprints)})+'\n')
    print('Built dist/: ' + str(len(fingerprints)) + ' public files')

if __name__ == '__main__':
    build()
