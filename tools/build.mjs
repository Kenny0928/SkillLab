// Regenerates the marked regions of index.html from content/*.mjs.
//   <!-- build:NAME:start --> ... <!-- build:NAME:end -->   (tabs, figs, side, traps)
// Run: node tools/build.mjs          (safe to re-run; an example whose 14 renders exist in assets/renders/ gets a 3D figure)
//      node tools/build.mjs --svg    (pure-SVG figures for every example)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderScene } from './lib/iso.mjs';
import robot from '../content/robot.mjs';
import drone from '../content/drone.mjs';
import parking from '../content/parking.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.join(here, '..', 'index.html');
const EXAMPLES = [robot, drone, parking]; // menu order
const SLOTS = [['sense', '感測'], ['decide', '判斷'], ['act', '執行'], ['record', '紀錄'], ['send', '傳送']];
const LOOP_LABEL = '互相影響';
const SVG_ONLY = process.argv.includes('--svg');

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
// split at each Chinese comma, keeping the comma with its phrase
const phrases = (s) => {
  const parts = s.split(/(?<=，)/);
  return parts.length > 1 ? parts.map((p) => `<span class="ph">${esc(p)}</span>`).join('') : esc(s);
};
const hid = (i) => (i === 0 ? '' : ' hidden');

// ---------- validation ----------
for (const ex of EXAMPLES) {
  const keys = SLOTS.map((s) => s[0]);
  for (const k of keys) if (!ex.slots[k]) throw new Error(`${ex.id}: missing slot ${k}`);
  if (ex.traps.length !== 5) throw new Error(`${ex.id}: need 5 traps`);
  for (const [a, b] of [...ex.edges, ...ex.loop.edges]) {
    if (!keys.includes(a) || !keys.includes(b)) throw new Error(`${ex.id}: bad edge ${a}->${b}`);
  }
  for (const [a, b] of ex.loop.edges) {
    if (!ex.edges.some(([x, y]) => x === a && y === b)) throw new Error(`${ex.id}: loop edge ${a}->${b} not in edges`);
  }
}

// ---------- network glyph ----------
const VBW = 240, VBH = 170, CX = 120, CY = 92, R = 80;
const ANGLE = { decide: -90, act: -18, record: 54, send: 126, sense: 198 }; // degrees, clockwise from +x
const NODE = {};
for (const [k, deg] of Object.entries(ANGLE)) {
  const t = (deg * Math.PI) / 180;
  NODE[k] = [CX + R * Math.cos(t), CY + R * Math.sin(t)];
}
const HW = 16 + 4, HH = 10 + 4; // label half box (largest displayed size) + gap
const f1 = (v) => v.toFixed(1);

function inset(from, to) {
  // point on the line from->to that leaves the label box of `from`
  let dx = to[0] - from[0], dy = to[1] - from[1];
  const L = Math.hypot(dx, dy); dx /= L; dy /= L;
  const t = Math.min(dx ? HW / Math.abs(dx) : Infinity, dy ? HH / Math.abs(dy) : Infinity);
  return [from[0] + dx * t, from[1] + dy * t];
}
function head(tip, from) {
  let dx = tip[0] - from[0], dy = tip[1] - from[1];
  const L = Math.hypot(dx, dy); dx /= L; dy /= L;
  const len = 6, w = 2.6;
  const bx = tip[0] - dx * len, by = tip[1] - dy * len;
  return `<polygon points="${f1(tip[0])},${f1(tip[1])} ${f1(bx - dy * w)},${f1(by + dx * w)} ${f1(bx + dy * w)},${f1(by - dx * w)}"/>`;
}

function glyph(ex) {
  const loopSet = new Set(ex.loop.edges.map(([a, b]) => a + '>' + b));
  const pairs = new Map(); // unordered pair -> list of directed edges
  for (const [a, b] of ex.edges) {
    const key = [a, b].sort().join('|');
    if (!pairs.has(key)) pairs.set(key, []);
    pairs.get(key).push([a, b]);
  }
  const g = [];
  for (const dirs of pairs.values()) {
    let [a, b] = dirs[0];
    const isLoop = dirs.some(([x, y]) => loopSet.has(x + '>' + y));
    // draw the line along the loop direction when it has one
    const l = dirs.find(([x, y]) => loopSet.has(x + '>' + y));
    if (l) [a, b] = l;
    const p = inset(NODE[a], NODE[b]);
    const q = inset(NODE[b], NODE[a]);
    const both = dirs.length > 1;
    g.push(
      `<g class="g-e" data-from="${a}" data-to="${b}"${isLoop ? ' data-loop="1"' : ''}>` +
        `<line x1="${f1(p[0])}" y1="${f1(p[1])}" x2="${f1(q[0])}" y2="${f1(q[1])}"/>` +
        head(q, p) + (both ? head(p, q) : '') + `</g>`
    );
  }
  const nodes = SLOTS.map(([k, label]) =>
    `<text data-slot="${k}" x="${f1(NODE[k][0])}" y="${f1(NODE[k][1])}" text-anchor="middle" dominant-baseline="central">${label}</text>`);
  return `<svg class="glyph" viewBox="0 0 ${VBW} ${VBH}" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">\n${g.join('\n')}\n${nodes.join('\n')}\n</svg>`;
}

// ---------- 3D figure: one render per step (assets/renders), the SVG laid over it as an overlay ----------
const STEPS = [0, 1, 2, 3, 4, 5, 6];
const renderFile = (id, n, x2 = false) => `${id}-s${n}${x2 ? '@2x' : ''}.webp`;
const missingRenders = (id) =>
  STEPS.flatMap((n) => [renderFile(id, n), renderFile(id, n, true)])
    .filter((f) => !fs.existsSync(path.join(here, '..', 'assets', 'renders', f)));

// The renders hold the solid parts, so the overlay drops them and keeps the rest: dashed paths and arrowheads,
// alignment lines and rotor rings (cone), the plate/screen text, and the callouts.
const SOLID = {
  polygon: ['f-top', 'f-left', 'f-right', 'plate', 'screen', 'wheel', 'ground', 'stop', 'loop'],
  line: ['detail', 'lane-edge'],
};
const DROP = [
  new RegExp(`<polygon class="(?:${SOLID.polygon.join('|')})"[^>]*/>`, 'g'),
  /<polygon style="[^"]*"[^>]*\/>/g, // the drone's painted shadows, the only polygon without a class
  new RegExp(`<line class="(?:${SOLID.line.join('|')})"[^>]*/>`, 'g'),
];
const DROPPED = new Set(['polygon[style]', ...Object.entries(SOLID).flatMap(([tag, cls]) => cls.map((c) => `${tag}.${c}`))]);
const EMPTY_G = /<g\b[^>]*>\s*<\/g>/g;

// element count by tag.class; a polygon with a style and no class counts as polygon[style]
function census(markup) {
  const n = new Map();
  for (const [, tag, attrs] of markup.matchAll(/<([a-z]+)\b([^>]*)>/g)) {
    const cls = attrs.match(/ class="([^"]*)"/);
    const key = tag + (cls ? '.' + cls[1] : / style="/.test(attrs) ? '[style]' : '');
    n.set(key, (n.get(key) || 0) + 1);
  }
  return n;
}

function overlayOf(inner) {
  let s = inner;
  for (const re of DROP) s = s.replace(re, '');
  for (let prev = null; prev !== s;) { prev = s; s = s.replace(EMPTY_G, ''); } // groups emptied by the above, nested ones too
  s = s.split('\n').filter((l) => l.trim()).join('\n'); // the removed groups leave blank lines
  // self-check: every dropped class is gone, nothing else was lost except emptied groups
  const before = census(inner), kept = census(s), removed = new Map();
  for (const [k, n] of before) {
    const left = kept.get(k) || 0;
    if (DROPPED.has(k) ? left !== 0 : k !== 'g' && left !== n) throw new Error(`overlay: ${k} ${n} before, ${left} after`);
    if (left < n) removed.set(k === 'g' ? 'g (emptied)' : k, n - left);
  }
  return { overlay: s, removed, kept };
}

const countList = (m) => [...m].sort(([a], [b]) => (a < b ? -1 : 1)).map(([k, n]) => `${k} ${n}`).join(', ');
const sum = (m) => [...m.values()].reduce((a, b) => a + b, 0);

function shotHtml(ex, r, overlay) {
  const imgs = STEPS.map((n) =>
    `<img class="shot-img" data-s="${n}" src="assets/renders/${renderFile(ex.id, n)}" ` +
    `srcset="assets/renders/${renderFile(ex.id, n)} ${r.w}w, assets/renders/${renderFile(ex.id, n, true)} ${2 * r.w}w" ` +
    `sizes="(max-width: 899px) 100vw, 60vw" width="${r.w}" height="${r.h}" alt="" loading="lazy" decoding="async">`);
  return (
    `<div class="shot" style="--ar: ${r.w} / ${r.h}">\n${imgs.join('\n')}\n` +
    `<svg class="model overlay" viewBox="0 0 ${r.w} ${r.h}" role="img" aria-label="${esc(ex.name)}示意圖" xmlns="http://www.w3.org/2000/svg">\n${overlay}\n</svg>\n</div>`
  );
}

// ---------- regions ----------
const regions = {};

regions.tabs =
  `<div class="tabs" role="tablist" aria-label="範例">\n` +
  EXAMPLES.map((ex, i) =>
    `  <button class="tab" role="tab" type="button" id="tab-${ex.id}" data-ex="${ex.id}" aria-selected="${i === 0}" aria-controls="fig-${ex.id}" tabindex="${i === 0 ? 0 : -1}">${esc(ex.name)}</button>`
  ).join('\n') + `\n</div>`;

const stats = [];
regions.figs = EXAMPLES.map((ex, i) => {
  const r = renderScene(ex.scene);
  const missing = missingRenders(ex.id);
  const use3d = !SVG_ONLY && missing.length === 0;
  const st = {
    id: ex.id, w: r.w, h: r.h, warnings: r.warnings,
    mode: use3d ? '3D (14 renders, SVG overlay)' : SVG_ONLY ? 'SVG (--svg)' : `SVG (${missing.length} of 14 renders missing: ${missing.join(', ')})`,
  };
  stats.push(st);
  let body = `<svg class="model" viewBox="0 0 ${r.w} ${r.h}" role="img" aria-label="${esc(ex.name)}示意圖" xmlns="http://www.w3.org/2000/svg">\n${r.inner}\n</svg>`;
  if (use3d) {
    const o = overlayOf(r.inner);
    Object.assign(st, { removed: o.removed, kept: o.kept });
    body = shotHtml(ex, r, o.overlay);
  }
  return (
    `<div class="fig-ex" id="fig-${ex.id}" role="tabpanel" aria-labelledby="tab-${ex.id}" data-ex="${ex.id}"${hid(i)}>\n` +
    `${body}\n</div>`
  );
}).join('\n');

regions.side = EXAMPLES.map((ex, i) => {
  const caps = SLOTS.map(([k, label]) =>
    `<div class="cap" aria-hidden="true">\n  <p class="lab">${label}</p>\n  <p class="sent">${phrases(ex.slots[k])}</p>\n</div>`);
  caps.push(`<div class="cap" aria-hidden="true">\n  <p class="lab">${LOOP_LABEL}</p>\n  <p class="sent">${phrases(ex.loop.sentence)}</p>\n</div>`);
  return `<div class="side-ex" data-ex="${ex.id}"${hid(i)}>\n${glyph(ex)}\n<div class="caps">\n${caps.join('\n')}\n</div>\n</div>`;
}).join('\n');

regions.traps = EXAMPLES.map((ex, i) =>
  `<ol class="reveal traps-list" data-ex="${ex.id}"${hid(i)}>\n` +
  ex.traps.map((t, n) => `  <li><span class="idx">${esc(ex.name)} 0${n + 1} / 05</span><p class="q">${phrases(t)}</p></li>`).join('\n') +
  `\n</ol>`
).join('\n');

// ---------- write ----------
let html = fs.readFileSync(htmlPath, 'utf8');
for (const [name, body] of Object.entries(regions)) {
  const re = new RegExp(`<!-- build:${name}:start -->[\\s\\S]*?<!-- build:${name}:end -->`);
  if (!re.test(html)) throw new Error(`markers for "${name}" not found in index.html`);
  html = html.replace(re, () => `<!-- build:${name}:start -->\n${body}\n<!-- build:${name}:end -->`);
}
fs.writeFileSync(htmlPath, html);

for (const s of stats) {
  console.log(s.id, 'viewBox', s.w, s.h, s.warnings.length ? 'WARN: ' + s.warnings.join('; ') : 'no label collisions (bbox test)');
  console.log(s.id, 'figure:', s.mode);
  if (s.removed) {
    console.log(`  overlay removed ${sum(s.removed)}: ${countList(s.removed)}`);
    console.log(`  overlay kept    ${sum(s.kept)}: ${countList(s.kept)}`);
  }
}
console.log('wrote', htmlPath);
