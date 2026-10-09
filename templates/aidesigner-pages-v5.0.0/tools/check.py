#!/usr/bin/env python3
"""Bounded checks of the actual publish artifact. Findings never print values."""
import gzip
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TARGET = (ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'dist')).resolve()
issues = []
def fail(path, rule):
    issues.append({'file':str(path.relative_to(TARGET)),'rule':rule})

class Document(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path, self.tags, self.ids, self.refs, self.metas = path, [], [], [], {}
        self.title_text = ''
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if a.get('id'): self.ids.append(a['id'])
        if tag == 'html' and not a.get('lang'): fail(self.path,'HTML language is missing')
        if tag == 'title': self.in_title = True
        if tag == 'meta': self.metas[a.get('name',a.get('http-equiv','')).lower()] = a.get('content','')
        if tag == 'img' and 'alt' not in a: fail(self.path,'Image needs alt text')
        if tag == 'button' and a.get('type') != 'button': fail(self.path,'Button needs explicit type=button')
        if tag == 'script' and not a.get('src'): fail(self.path,'Inline script requires normalization to a local asset')
        if tag in {'iframe','object','embed','form'}: fail(self.path,'Unapproved embed or data-collection surface')
        if tag == 'style' or 'style' in a: fail(self.path,'Inline styles require normalization to a local asset')
        if any(k.lower().startswith('on') for k in a): fail(self.path,'Inline event handler')
        for k in ('href','src'):
            if k not in a: continue
            v = a[k].strip()
            u = urlsplit(v)
            if u.scheme and u.scheme != 'https': fail(self.path,'Unsafe or unapproved URL scheme')
            if tag in {'script','img','link'} and u.netloc and not (tag == 'link' and a.get('rel') == 'canonical'):
                fail(self.path,'Runtime assets must be local')
            if not u.netloc and not u.scheme: self.refs.append(v)
            if a.get('target') == '_blank' and 'noopener' not in a.get('rel',''): fail(self.path,'New window link lacks noopener')
    def handle_endtag(self,tag):
        if tag == 'title': self.in_title = False
    def handle_data(self,data):
        if self.in_title: self.title_text += data

if not TARGET.is_dir():
    raise SystemExit('Build dist/ before checking')
total = 0
patterns = {
    'Private key material': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'GitHub credential pattern': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})'),
    'Google API credential pattern': re.compile(r'AIza[0-9A-Za-z_-]{35}'),
    'OpenAI credential pattern': re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
    'Private device address or host': re.compile(r'\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|localhost|[\w.-]+\.ts\.net)\b',re.I),
    'Email address in public source': re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
    'Dangerous JavaScript execution': re.compile(r'\beval\s*\(|\bnew\s+Function\s*\(|\.innerHTML\s*='),
    'Published placeholder marker': re.compile(r'\bTODO\b|lorem ipsum|example\.com|YOUR_(?:TOKEN|KEY|DOMAIN)',re.I),
}
for p in sorted(TARGET.rglob('*')):
    if p.is_symlink(): fail(p,'Symlink in artifact')
    if not p.is_file(): continue
    data = p.read_bytes()
    total += len(gzip.compress(data))
    if p.suffix in {'.map','.py','.sh','.zip','.json','.yml','.yaml','.md'} or p.name.startswith('.env'):
        fail(p,'Source or private working file in public artifact')
    if p.suffix.lower() not in {'.html','.css','.js','.svg','.txt','.xml'}: continue
    text = data.decode('utf-8')
    for name,pattern in patterns.items():
        if pattern.search(text): fail(p,name)
    if p.suffix == '.css' and re.search(r'@import|url\(\s*[\"\x27]?https?://',text,re.I): fail(p,'Network-loaded CSS asset')
    if p.suffix != '.html': continue
    doc = Document(p)
    doc.feed(text)
    if not text.lower().lstrip().startswith('<!doctype html>'): fail(p,'Missing HTML5 doctype')
    if doc.tags.count('h1') != 1: fail(p,'Expected one h1')
    if not doc.title_text.strip(): fail(p,'Page title is missing')
    for t in ('header','nav','main','footer'):
        if t not in doc.tags: fail(p,'Missing semantic '+t)
    if len(doc.ids) != len(set(doc.ids)): fail(p,'Duplicate element IDs')
    for m in ('viewport','description','content-security-policy','referrer'):
        if not doc.metas.get(m): fail(p,'Missing metadata: '+m)
    csp = doc.metas.get('content-security-policy','')
    if "'unsafe-inline'" in csp or "'unsafe-eval'" in csp: fail(p,'Unsafe CSP bypass')
    if 'frame-ancestors' in csp: fail(p,'frame-ancestors cannot be enforced in a meta policy')
    for ref in doc.refs:
        u = urlsplit(ref)
        destination = (p.parent / unquote(u.path)).resolve() if u.path else p.resolve()
        if not destination.is_relative_to(TARGET): fail(p,'Link escapes the Pages project root')
        elif not destination.exists(): fail(p,'Broken local link or asset')
        elif u.fragment and destination == p.resolve() and unquote(u.fragment) not in doc.ids: fail(p,'Broken same-page anchor')
if total > 100*1024: fail(TARGET/'index.html','Combined gzip budget exceeds 100 KiB')
report = {'time':datetime.now(timezone.utc).isoformat(),'gate':'VERIFY','passed':not issues,'gzip_bytes':total,'findings':issues,'scope':'built artifact only; not a repository-history audit or security guarantee'}
evidence = ROOT/'.evidence'
evidence.mkdir(exist_ok=True)
(evidence/'checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
with (evidence/'events.jsonl').open('a',encoding='utf-8') as ledger: ledger.write(json.dumps({'time':report['time'],'gate':'VERIFY','event':'artifact_checks','passed':report['passed'],'findings':len(issues)})+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(1 if issues else 0)
