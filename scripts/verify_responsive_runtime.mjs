#!/usr/bin/env node
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { spawn } from 'node:child_process';

const ROOT = new URL('../public/', import.meta.url).pathname;
const PORT = 4173;
const HOST = '127.0.0.1';

const TARGETS = [
  '/',
  '/plant-profiles/',
  '/plant-profiles/monstera-albo/',
  '/posts/monstera-node-vs-axillary-bud-variegated-cutting/',
  '/plant-problems/turning-green/',
  '/variegated-monstera/',
  '/buying-guides/best-selling-grow-lights/'
];

const MOBILE_GRID_SELECTORS = [
  '.editorial-visual-grid',
  '.editorial-action-grid',
  '.editorial-related-grid',
  '.profile-link-grid',
  '.problem-related-grid',
  '.problem-step-grid',
  '.hub-card-grid',
  '.hub-related-grid',
  '.profile-index-grid',
  '.profile-index-links',
  '.home-path-grid',
  '.home-path-grid-visual',
  '.home-latest-grid',
  '.profile-two-col',
  '.problem-two-col',
  '.profile-care-grid'
];

const CARD_SELECTORS = [
  '.editorial-visual-card',
  '.editorial-action-card',
  '.editorial-related-grid a',
  '.profile-link-grid a',
  '.problem-related-grid a',
  '.problem-step-card',
  '.hub-guide-card',
  '.hub-related-grid a',
  '.profile-index-card',
  '.profile-index-links a',
  '.home-path-card'
];

const mime = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon'
};

function safePublicPath(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]);
  let rel = clean.replace(/^\/+/, '');
  if (!rel || rel.endsWith('/')) rel += 'index.html';
  const abs = normalize(join(ROOT, rel));
  if (!abs.startsWith(normalize(ROOT))) return null;
  return abs;
}

function testHarnessHtml() {
  const tests = [];
  for (const path of TARGETS) {
    tests.push({ path, width: 390, mode: 'mobile' });
    tests.push({ path, width: 1366, mode: 'desktop' });
  }
  return `<!doctype html><html><head><meta charset="utf-8"><title>responsive-test</title></head><body>
<script>
const tests = ${JSON.stringify(tests)};
const gridSelectors = ${JSON.stringify(MOBILE_GRID_SELECTORS)};
const cardSelectors = ${JSON.stringify(CARD_SELECTORS)};

function visible(el) {
  const s = getComputedStyle(el);
  return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length > 0;
}

function countGridColumns(value) {
  if (!value || value === 'none') return 0;
  // Computed gridTemplateColumns is a space-separated list of resolved tracks.
  return value.trim().split(/\\s+/).filter(Boolean).length;
}

async function inspect(test) {
  return await new Promise((resolve) => {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:absolute;left:-20000px;top:0;border:0;height:1200px;';
    iframe.width = String(test.width);
    iframe.src = test.path + (test.path.includes('?') ? '&' : '?') + '__responsive_test=1';
    document.body.appendChild(iframe);
    const timer = setTimeout(() => resolve({path:test.path,width:test.width,error:'timeout'}), 12000);
    iframe.onload = () => {
      try {
        const win = iframe.contentWindow;
        const doc = iframe.contentDocument;
        const vw = win.innerWidth;
        const sw = doc.documentElement.scrollWidth;
        const result = { path:test.path, width:test.width, mode:test.mode, viewport:vw, scrollWidth:sw, errors:[] };

        if (sw > vw + 2) result.errors.push('horizontal-overflow:' + sw + '>' + vw);

        const offenders = [];
        for (const el of doc.querySelectorAll('body *')) {
          if (!visible(el)) continue;
          const style = win.getComputedStyle(el);
          if (style.position === 'fixed' || style.position === 'sticky') continue;
          const r = el.getBoundingClientRect();
          if (r.width <= 0 || r.height <= 0) continue;
          if (r.left < -3 || r.right > vw + 3) {
            offenders.push((el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().replace(/\\s+/g,'.') : '')).slice(0,160));
            if (offenders.length >= 8) break;
          }
        }
        if (offenders.length) result.errors.push('offscreen-elements:' + offenders.join('|'));

        if (test.mode === 'mobile') {
          for (const selector of gridSelectors) {
            for (const grid of doc.querySelectorAll(selector)) {
              if (!visible(grid)) continue;
              const cols = countGridColumns(win.getComputedStyle(grid).gridTemplateColumns);
              if (cols > 1) result.errors.push('mobile-grid-columns:' + selector + ':' + cols);
            }
          }
          for (const selector of cardSelectors) {
            for (const card of doc.querySelectorAll(selector)) {
              if (!visible(card)) continue;
              const width = card.getBoundingClientRect().width;
              if (width > 0 && width < 250) result.errors.push('narrow-mobile-card:' + selector + ':' + Math.round(width));
            }
          }
        }
        clearTimeout(timer);
        iframe.remove();
        resolve(result);
      } catch (err) {
        clearTimeout(timer);
        iframe.remove();
        resolve({path:test.path,width:test.width,error:String(err)});
      }
    };
  });
}

(async () => {
  const results = [];
  for (const test of tests) results.push(await inspect(test));
  document.body.dataset.result = encodeURIComponent(JSON.stringify(results));
  document.body.textContent = 'done';
})();
</script></body></html>`;
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${HOST}:${PORT}`);
    if (url.pathname === '/__responsive_test_runner') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
      res.end(testHarnessHtml());
      return;
    }
    const path = safePublicPath(url.pathname);
    if (!path) {
      res.writeHead(400); res.end('bad path'); return;
    }
    const s = await stat(path);
    if (!s.isFile()) throw new Error('not file');
    const data = await readFile(path);
    res.writeHead(200, { 'content-type': mime[extname(path).toLowerCase()] || 'application/octet-stream', 'cache-control': 'no-store' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain' });
    res.end('not found');
  }
});

function findChrome() {
  const candidates = [
    process.env.CHROME_BIN,
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser'
  ].filter(Boolean);
  return candidates.find(existsSync);
}

function runChrome(chrome) {
  return new Promise((resolve, reject) => {
    const args = [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--hide-scrollbars',
      '--window-size=1600,1200',
      '--virtual-time-budget=30000',
      '--dump-dom',
      `http://${HOST}:${PORT}/__responsive_test_runner`
    ];
    const child = spawn(chrome, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    let err = '';
    child.stdout.on('data', d => out += d);
    child.stderr.on('data', d => err += d);
    child.on('error', reject);
    child.on('close', code => {
      if (code !== 0) reject(new Error(`Chrome exited ${code}: ${err.slice(-2000)}`));
      else resolve(out);
    });
  });
}

await new Promise(resolve => server.listen(PORT, HOST, resolve));
try {
  const chrome = findChrome();
  if (!chrome) throw new Error('Chrome/Chromium not found on CI runner; responsive test cannot run.');
  const dom = await runChrome(chrome);
  const match = dom.match(/data-result="([^"]+)"/);
  if (!match) throw new Error('Responsive test runner did not produce results.');
  const results = JSON.parse(decodeURIComponent(match[1].replaceAll('&amp;', '&')));
  const failures = results.filter(r => r.error || (r.errors && r.errors.length));
  if (failures.length) {
    console.error('Responsive runtime FAIL');
    for (const f of failures) console.error(JSON.stringify(f));
    process.exitCode = 1;
  } else {
    console.log(`Responsive runtime PASS: ${results.length} viewport/page combinations checked; no clipping, horizontal overflow or multi-column phone cards.`);
  }
} finally {
  server.close();
}
