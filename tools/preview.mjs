// Renders one scene at every teardown step into a standalone HTML page, without touching index.html.
// Run: node tools/preview.mjs <robot|drone|parking> [outDir]   -> <outDir>/preview-<id>.html
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { renderScene } from './lib/iso.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const id = process.argv[2];
const outDir = path.resolve(process.argv[3] || '.');
const ex = (await import(pathToFileURL(path.join(here, '..', 'content', id + '.mjs')).href)).default;
const r = renderScene(ex.scene);
const css = pathToFileURL(path.join(here, '..', 'assets', 'style.css')).href;
const names = ['0', '1 感測', '2 判斷', '3 執行', '4 紀錄', '5 傳送', '6 互相影響'];
const cells = names.map((n, s) => `<section class="stage" data-step="${s}"><p class="pv">${n}</p><div class="fig"><div class="fig-ex"><svg class="model" viewBox="0 0 ${r.w} ${r.h}" xmlns="http://www.w3.org/2000/svg">${r.inner}</svg></div></div></section>`).join('\n');
fs.mkdirSync(outDir, { recursive: true });
const file = path.join(outDir, `preview-${id}.html`);
fs.writeFileSync(file, `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="${css}">
<style>.stage{position:static!important;height:auto!important;display:block!important;padding:16px;border-bottom:1px solid var(--rule)}.fig{width:100%!important;max-width:900px}.model{max-height:none!important}.pv{font:13px var(--mono);color:var(--ink-2)}</style>
<body data-ex="${id}">${cells}</body>`);
console.log(file, `viewBox ${r.w}x${r.h}`);
console.log(r.warnings.length ? 'WARNINGS:\n' + r.warnings.join('\n') : 'no label collisions');
