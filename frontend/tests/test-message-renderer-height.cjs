// Exercise the real renderer script with independent content and viewport sizes.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(process.argv[2] || path.join(__dirname, '../resources/message_renderer/index.html'), 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
let height = 42, observer, publications = [];
const content = { innerHTML: '', getBoundingClientRect: () => ({ height }), querySelectorAll: () => [] };
const document = { getElementById: () => content,
  documentElement: { scrollHeight: 700, style: { setProperty() {} } },
  set title(value) { publications.push(value); } };
const md = { use() {}, renderer: { rules: { fence() {} } }, render: String, utils: { escapeHtml: String } };
const window = { markdownit: () => md, addEventListener() {} };
vm.runInNewContext(script, { document, window, mermaid: { initialize() {} },
  ResizeObserver: class { constructor(fn) { observer = fn; } observe() {} } });
(async () => {
  await window.renderMarkdown('A readable message', 1);
  assert.equal(publications.at(-1), 'pixiu-height:42:1', 'height must come from content, not the web viewport');
  const count = publications.length;
  for (let i = 0; i < 20; ++i) { document.documentElement.scrollHeight += 2; observer(); }
  assert.equal(publications.length, count, 'viewport resize must not feed back into message height');
  height = 28;
  await window.renderMarkdown('short', 2);
  assert.equal(publications.at(-1), 'pixiu-height:28:2', 'shorter content must be allowed to shrink');
  await window.renderMarkdown('same height new revision', 3);
  assert.equal(publications.at(-1), 'pixiu-height:28:3', 'new content must acknowledge its own revision');
  assert.ok(!html.includes('font-display: block'), 'fonts must not hide readable fallback text');
  console.log('renderer height regression: OK');
})().catch(error => { console.error(error); process.exit(1); });
