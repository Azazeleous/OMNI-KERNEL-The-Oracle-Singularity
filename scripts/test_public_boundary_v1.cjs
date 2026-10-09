const assert = require('node:assert/strict');
const boundary = require('../security/public-boundary-v1.js');
assert.throws(() => boundary.text('<img src=x onerror=alert(1)>'), /Unlabelled/);
assert.throws(() => String(boundary.taint('secret', 'external')), /explicit/);
const adversarial = '<img src=x onerror=alert(1)>';
assert.equal(boundary.text(boundary.taint(adversarial, 'api-response')), adversarial);
for (const url of ['javascript:alert(1)', 'data:text/html,test', 'http://example.com', 'https://user:pass@example.com', 'https://127.0.0.1', 'https://192.168.1.1', 'https://[::1]', 'https://host.ts.net', 'https://localhost', 'https://0x7f000001', 'https://2130706433']) {
  assert.throws(() => boundary.safeLink(boundary.taint(url, 'citation')));
}
assert.equal(boundary.safeLink(boundary.taint('https://example.com/path', 'citation')), 'https://example.com/path');
assert.throws(() => boundary.safeLink(boundary.taint('https://example.com/?token=private', 'citation')));
assert.throws(() => boundary.safeLink(boundary.taint('https://notebooklm.google.com/notebook/private', 'citation')));
assert.throws(() => boundary.endpoint(boundary.taint('__proto__', 'control')));
assert.throws(() => boundary.endpoint(boundary.taint('../private', 'control')));
assert.deepEqual(boundary.endpoint(boundary.taint('status', 'control')), { path: '/api/status', method: 'GET' });
console.log('Public-boundary adversarial validation tests passed. Browser rendering remains a separate check.');
