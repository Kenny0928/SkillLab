// Full-page screenshots of a site page through headless Chrome; serves the repo itself, no server needed.
// node .claude/skills/check-layout/shot.mjs <page.html> [--out DIR] [--widths 1440,900,390] [--selector CSS] [--eval "JS"]
//   --selector  capture only the first matching element (plus 16px around it)
//   --eval      print the value of a JS expression after the page settles, once per width
// Writes <out>/<page>-<width>.png; phone widths (< 600) at 2x.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf('--' + name); return i < 0 ? def : args.splice(i, 2)[1]; };
const out = path.resolve(opt('out', os.tmpdir()));
const widths = opt('widths', '1440,900,390').split(',').map(Number);
const selector = opt('selector', '');
const evalExpr = opt('eval', '');
const page = args[0];
if (!page) { console.error('usage: shot.mjs <page.html> [--out DIR] [--widths 1440,900,390] [--selector CSS] [--eval "JS"]'); process.exit(1); }

const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg' };
const server = http.createServer((req, res) => {
  let p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (p.endsWith('/')) p += 'index.html';
  if (!p.startsWith(root) || !fs.existsSync(p)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
}).listen(0);
const url = `http://127.0.0.1:${server.address().port}/${page}`;

const port = 9500 + Math.floor(Math.random() * 400);
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--hide-scrollbars', `--remote-debugging-port=${port}`, `--user-data-dir=${os.tmpdir()}/shot-${port}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let list; for (let i = 0; i < 50 && !list; i++) { try { list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); } catch { await sleep(200); } }
const ws = new WebSocket(list.find(t => t.type === 'page').webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(); ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async x => (await send('Runtime.evaluate', { expression: x, returnByValue: true, awaitPromise: true })).result?.result?.value;
await send('Page.enable');

fs.mkdirSync(out, { recursive: true });
const name = path.basename(page, '.html');
for (const W of widths) {
  const scale = W < 600 ? 2 : 1, mobile = W < 600;
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: 900, deviceScaleFactor: scale, mobile });
  await send('Page.navigate', { url });
  for (let i = 0; i < 50 && await ev('document.readyState') !== 'complete'; i++) await sleep(100);
  await ev('document.fonts.ready.then(() => 1)');
  const h0 = await ev('document.documentElement.scrollHeight');
  for (let y = 0; y < h0; y += 800) { await ev(`scrollTo(0, ${y})`); await sleep(40); } // load lazy images
  await ev('scrollTo(0, 0)'); await sleep(400);
  const H = await ev('document.documentElement.scrollHeight');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: scale, mobile });
  await sleep(400);
  // clientWidth, not innerWidth: under phone emulation innerWidth grows with an overflowing page
  const overflow = await ev('document.documentElement.scrollWidth - document.documentElement.clientWidth');
  let clip;
  if (selector) {
    const r = await ev(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; const b = e.getBoundingClientRect(); return { x: Math.max(0, b.left - 16), y: Math.max(0, b.top + scrollY - 16), width: Math.min(innerWidth, b.width + 32), height: b.height + 32 }; })()`);
    if (!r) { console.error(`${W}px: no element matches ${selector}`); continue; }
    clip = { ...r, scale: 1 };
  }
  if (evalExpr) console.log(`${W}px eval:`, JSON.stringify(await ev(evalExpr)));
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, ...(clip && { clip }) });
  const file = path.join(out, `${name}-${W}${selector ? '-part' : ''}.png`);
  fs.writeFileSync(file, Buffer.from(shot.result.data, 'base64'));
  console.log(`${file}  ${W}x${clip ? Math.round(clip.height) : H}${overflow > 0 ? `  ⚠ horizontal overflow ${overflow}px` : ''}`);
}
ws.close(); chrome.kill(); server.close();
process.exit(0);
