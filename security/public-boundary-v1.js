/* TDOC PUBLIC-BOUNDARY v1.0.0 — explicit data provenance and safe DOM sinks. */
(function (root) {
  'use strict';
  const labels = new WeakMap();
  function taint(value, source) {
    if (typeof source !== 'string' || !source || source.length > 128) throw new TypeError('Source label required');
    const box = Object.freeze({ toString() { throw new TypeError('Use an explicit validated sink'); } });
    labels.set(box, { value, source });
    return box;
  }
  function unwrap(box) {
    if (!labels.has(box)) throw new TypeError('Unlabelled input rejected');
    return labels.get(box).value;
  }
  function text(box, maximum = 8192) {
    const value = unwrap(box);
    if (typeof value !== 'string' && typeof value !== 'number') throw new TypeError('Scalar text required');
    const result = String(value);
    if (result.length > maximum) throw new RangeError('Text exceeds limit');
    return result;
  }
  function renderText(element, box) { element.textContent = text(box); }
  function safeLink(box) {
    const value = text(box, 2048);
    if (/[\u0000-\u0020\u007f]/.test(value)) throw new TypeError('URL control characters rejected');
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password) throw new TypeError('Public HTTPS URL required');
    const host = url.hostname.toLowerCase();
    if (/^(?:localhost|\d+(?:\.\d+){3}|\[)/.test(host) || /\.(?:local|internal|invalid|ts\.net)$/.test(host)) throw new TypeError('Private host rejected');
    if (/^(?:notebooklm|colab\.research|drive|docs)\.google\.com$/.test(host)) throw new TypeError('Private workspace links require separate review');
    for (const key of url.searchParams.keys()) {
      if (/token|secret|password|credential|signature|session|^key$|^code$|auth/i.test(key)) throw new TypeError('Credential-bearing query rejected');
    }
    return url.href;
  }
  const endpoints = Object.freeze({ status: 'GET', gemini: 'GET', vision: 'POST', 'gaia-node': 'GET', voice: 'POST', audio: 'POST', 'fs-scan': 'POST', notebooklm: 'GET', aistudio: 'GET' });
  function endpoint(box) {
    const name = text(box, 32);
    if (!Object.hasOwn(endpoints, name)) throw new TypeError('Unknown endpoint');
    return Object.freeze({ path: '/api/' + name, method: endpoints[name] });
  }
  const api = Object.freeze({ taint, text, renderText, safeLink, endpoint });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.defineProperty(root, 'NexusBoundary', { value: api, writable: false });
})(typeof globalThis === 'object' ? globalThis : this);
