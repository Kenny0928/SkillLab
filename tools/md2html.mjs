// Turns a handout written in Markdown (content/handout/<slug>.md) into handout/<slug>.html.
// The markup is described in .claude/skills/handout/markup.md.
//   node tools/md2html.mjs <slug>             publish: write handout/<slug>.html, fill code blocks, sync the menu card
//   node tools/md2html.mjs <slug> --preview   write handout/_preview-<slug>.html (git-ignored); [待查] is shown
//                                             highlighted, missing diagrams become placeholders, the menu is untouched
// Publishing refuses while the Markdown still has [待查], a note to Claude, or a diagram that is not drawn yet.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { noBreak } from './lib/nobreak.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');
const args = process.argv.slice(2);
const slug = args.find(a => !a.startsWith('--'));
const PREVIEW = args.includes('--preview');
if (!slug) { console.error('usage: node tools/md2html.mjs <slug> [--preview]'); process.exit(1); }

const mdPath = path.join(root, 'content', 'handout', slug + '.md');
const figDir = path.join(root, 'assets', 'handout', 'fig', slug);
const credits = JSON.parse(fs.readFileSync(path.join(root, 'assets', 'handout', 'img', 'credits.json'), 'utf8'));

const TYPE_NAME = { tool: '工具', hardware: '硬體', concept: '觀念', project: '微專題', advanced: '進階專題', resource: '學習資源' };
// product names that must not break across lines (CLAUDE.md); longest first
const JOIN = ['AI Thinker ESP32-CAM', 'XIAO ESP32-S3 Sense', 'Teachable Machine', 'Raspberry Pi', 'Arduino IDE', 'Arduino Uno', 'VS Code'];
const CJK = /[⺀-鿿　-〿＀-￯]/;

const problems = [];   // block publishing
const warnings = [];   // printed, do not block
const usedImages = [];

// ---------- inline ----------

const esc = s => s.replace(/&(?!#?\w+;)/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escAttr = s => esc(s).replace(/"/g, '&quot;');
const plain = s => s.replace(/`([^`]+)`/g, '$1').replace(/\*\*(.+?)\*\*/g, '$1').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');

function inline(s, ctx = {}) {
  return s.split(/(`[^`]+`)/).map((part, i) => {
    if (i % 2) {
      if (part.length > 32 && !ctx.table) warnings.push('行內程式碼太長，手機上會撐出橫向捲動，改用 ```sh 區塊：' + part);
      const code = esc(part.slice(1, -1));
      return ctx.table ? `<span class="pin">${code}</span>` : `<code>${code}</code>`;
    }
    let t = esc(part);
    for (const name of JOIN) t = t.split(name).join(name.replace(/ /g, '&nbsp;'));
    t = t.replace(/\[待查\]/g, () => {
      if (!PREVIEW) problems.push('還有 [待查]');
      return '<mark>[待查]</mark>';
    });
    t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, href) =>
      /^https?:/.test(href) ? `<a href="${href}" target="_blank" rel="noopener">${text}</a>` : `<a href="${href}">${text}</a>`);
    t = t.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    return t;
  }).join('');
}

// join wrapped lines: no space between Chinese characters
const joinLines = ls => ls.map(l => l.trim()).reduce((a, l) => !a ? l : CJK.test(a.at(-1)) || CJK.test(l[0]) ? a + l : a + ' ' + l, '');

// "**標籤**：內容" → ['標籤', '內容']
const labelled = s => { const m = s.match(/^\*\*(.+?)\*\*[：:]\s*(.*)$/s); return m ? [m[1], m[2]] : null; };

// "標題 {#id}" → ['標題', 'id']
const withId = s => { const m = s.match(/^(.*?)\s*\{#([\w-]+)\}\s*$/); return m ? [m[1], m[2]] : [s.trim(), null]; };

// ---------- blocks ----------

const isFence = l => /^\s*```/.test(l);
const containerOpen = l => l.match(/^(:{3,})(\w+)\s*(.*)$/);
const listItem = l => l.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
const startsBlock = l => /^(#{2,4}\s|```|:{3,}\w|@code\s|\||>|<!--)/.test(l) || listItem(l);

function parseBlocks(lines) {
  const nodes = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    if (isFence(line)) {
      const lang = line.trim().slice(3).trim();
      const body = [];
      i++;
      while (i < lines.length && !isFence(lines[i])) body.push(lines[i++]);
      i++;
      nodes.push({ t: 'fence', lang, code: body.join('\n') });
      continue;
    }
    const c = containerOpen(line);
    if (c) {
      const close = c[1];
      const body = [];
      let inFence = false;
      i++;
      while (i < lines.length && !(lines[i].trim() === close && !inFence)) {
        if (isFence(lines[i])) inFence = !inFence;
        body.push(lines[i++]);
      }
      if (i >= lines.length) warnings.push(`區塊 ${c[2]} 沒有結尾的 ${close}`);
      i++;
      nodes.push({ t: 'box', name: c[2], arg: c[3].trim(), lines: body });
      continue;
    }
    if (line.startsWith('<!--')) {
      const body = [line];
      while (!lines[i].includes('-->') && i + 1 < lines.length) body.push(lines[++i]);
      i++;
      const text = body.join('\n');
      if (/給 Claude/.test(text) && !PREVIEW) problems.push('還有給 Claude 的指示：' + text.replace(/\s+/g, ' ').slice(0, 60));
      continue;  // comments never reach the page
    }
    if (/^<[a-zA-Z]/.test(line)) {  // raw HTML passes through until a blank line
      const body = [];
      while (i < lines.length && lines[i].trim()) body.push(lines[i++]);
      nodes.push({ t: 'html', html: body.join('\n') });
      continue;
    }
    const h = line.match(/^(#{2,4})\s+(.*)$/);
    if (h) {
      const [text, id] = withId(h[2]);
      nodes.push({ t: 'h', level: h[1].length, text, id });
      i++;
      continue;
    }
    const code = line.match(/^@code\s+(\S+)(?:\s+name=(\S+))?\s*$/);
    if (code) { nodes.push({ t: 'code', file: code[1], name: code[2] }); i++; continue; }
    if (line.startsWith('|') && /^\|?\s*:?-{3,}/.test(lines[i + 1] || '')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) rows.push(lines[i++]);
      const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(s => s.trim());
      nodes.push({ t: 'table', head: cells(rows[0]), rows: rows.slice(2).map(cells) });
      continue;
    }
    if (line.startsWith('>')) {
      const body = [];
      while (i < lines.length && lines[i].startsWith('>')) body.push(lines[i++].replace(/^>\s?/, ''));
      nodes.push({ t: 'quote', lines: body });
      continue;
    }
    const li = listItem(line);
    if (li && li[1].length === 0) {
      const ordered = /\d/.test(li[2]);
      const items = [];
      while (i < lines.length) {
        const m = listItem(lines[i]);
        if (m && m[1].length === 0) { items.push({ text: [m[3]], sub: [] }); i++; continue; }
        if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length) {
          const item = items.at(-1);
          const sm = listItem(lines[i]);
          if (sm || item.sub.length) item.sub.push(lines[i].replace(/^\s{2,4}/, ''));
          else item.text.push(lines[i]);
          i++;
          continue;
        }
        break;
      }
      nodes.push({ t: 'list', ordered, items: items.map(it => ({ text: joinLines(it.text), sub: it.sub })) });
      continue;
    }
    const body = [];
    while (i < lines.length && lines[i].trim() && !(body.length && startsBlock(lines[i]))) body.push(lines[i++]);
    nodes.push({ t: 'p', lines: body });
  }
  return nodes;
}

// ---------- render ----------

function imageSize(file) {
  const c = credits.find(e => e.file === path.basename(file));
  if (c) return [c.width, c.height];
  try {
    const b = fs.readFileSync(path.join(root, 'handout', file));
    if (b.toString('ascii', 1, 4) === 'PNG') return [b.readUInt32BE(16), b.readUInt32BE(20)];
    if (b.toString('ascii', 8, 12) === 'WEBP') {
      const kind = b.toString('ascii', 12, 16);
      if (kind === 'VP8 ') return [b.readUInt16LE(26) & 0x3fff, b.readUInt16LE(28) & 0x3fff];
      if (kind === 'VP8L') { const v = b.readUInt32LE(21); return [(v & 0x3fff) + 1, ((v >> 14) & 0x3fff) + 1]; }
      if (kind === 'VP8X') return [b.readUIntLE(24, 3) + 1, b.readUIntLE(27, 3) + 1];
    }
  } catch {}
  warnings.push('量不到圖片尺寸：' + file);
  return null;
}

function list(node, ctx) {
  const tag = node.ordered ? 'ol' : 'ul';
  return `<${tag} class="prose">\n` + node.items.map(it =>
    `<li>${inline(it.text, ctx)}${it.sub.length ? '\n' + render(parseBlocks(it.sub), ctx) : ''}</li>`).join('\n') + `\n</${tag}>`;
}

function table(node, ctx) {
  const head = node.head.map(h => h ? `<th scope="col">${inline(h, { table: true })}</th>` : '<th></th>').join('');
  const rows = node.rows.map(r => '<tr>' + r.map((cell, k) => k === 0
    ? `<th scope="row">${inline(cell, { table: true })}</th>`
    : `<td data-label="${escAttr(plain(node.head[k] || ''))}">${inline(cell, { table: true })}</td>`).join('') + '</tr>').join('\n');
  return `<div class="table-wrap${lead(ctx)}"><table class="tbl stack"><thead><tr>${head}</tr></thead><tbody>\n${rows}\n</tbody></table></div>`;
}

function codeBar(name, label) {
  return `<div class="code-bar"><span class="code-name">${esc(name)}</span><button class="copy" type="button" aria-label="複製 ${escAttr(label)}">複製</button></div>`;
}

function fence(node) {
  const first = node.code.split('\n')[0].slice(0, 40);
  if (node.lang === 'sh') {
    return `<div class="code" data-lang="sh">\n${codeBar('終端機', first)}\n<pre tabindex="0"><code data-lang="sh">${esc(node.code)}</code></pre>\n</div>`;
  }
  if (node.lang === 'prompt') {
    return `<div class="code prompt" data-lang="plain">\n${codeBar('提示詞', '提示詞：' + first)}\n<pre tabindex="0"><code data-lang="plain">${esc(node.code)}</code></pre>\n</div>`;
  }
  const lang = { py: 'py', python: 'py', ino: 'ino', cpp: 'ino', json: 'json', js: 'js' }[node.lang] || 'plain';
  return `<div class="code" data-lang="${lang}">\n${codeBar(node.lang || '程式', first)}\n<pre tabindex="0"><code data-lang="${lang}">${esc(node.code)}</code></pre>\n</div>`;
}

function quote(node) {
  const text = node.lines.join('\n');
  if (/^\[!NOTE\]/.test(text)) {
    return text.replace(/^\[!NOTE\]\s*/, '').split(/\n\s*\n/).filter(s => s.trim())
      .map(p => `<p class="note">${inline(joinLines(p.split('\n')))}</p>`).join('\n');
  }
  if (/^「/.test(text)) return `<p class="lead-q">${inline(joinLines(node.lines))}</p>`;
  warnings.push('引言不是 [!NOTE] 也不是「」問題，當成補充：' + text.slice(0, 30));
  return `<p class="note">${inline(joinLines(node.lines))}</p>`;
}

function paragraph(node, ctx) {
  const img = node.lines[0].match(/^!\[([^\]]*)\]\(([^)\s]+)\)$/);
  if (img) {
    const cap = node.lines[1]?.match(/^\*(.+)\*$/);
    const size = imageSize(img[2]);
    usedImages.push({ file: path.basename(img[2]), label: cap ? plain(cap[1]) : img[1] });
    return `<figure class="figure${lead(ctx)}"><img src="${img[2]}" alt="${escAttr(img[1])}"${size ? ` width="${size[0]}" height="${size[1]}"` : ''} loading="lazy">` +
      (cap ? `<figcaption>${inline(cap[1])}</figcaption>` : '') + '</figure>';
  }
  return `<p>${inline(joinLines(node.lines), ctx)}</p>`;
}

// the first big element of a section (before any h3) gets .lead-in
function lead(ctx) {
  if (!ctx.sec || ctx.sec.leadDone || ctx.nested) return '';
  ctx.sec.leadDone = true;
  return ' lead-in';
}

// ---------- boxes (:::name) ----------

function itemsOf(lines) {
  const nodes = parseBlocks(lines).filter(n => n.t === 'list');
  return nodes.flatMap(n => n.items);
}

const BOX = {
  fold(node, ctx) {
    const m = node.arg.match(/^(教學|AI)\s+(.*)$/);
    const summary = m ? `<span><span class="tag">${m[1]}</span>${inline(m[2])}</span>` : node.arg === '常見問題' ? '常見問題' : `<span>${inline(node.arg)}</span>`;
    const body = render(parseBlocks(node.lines), { ...ctx, fold: true, nested: true });
    return `<details class="fold${m?.[1] === 'AI' ? ' ai' : ''}">\n<summary>${summary}</summary>\n<div class="fold-body">\n${body}\n</div>\n</details>`;
  },
  qa(node, ctx) {
    const rows = itemsOf(node.lines).map(it => {
      const [label, rest] = labelled(it.text) || ['', it.text];
      const sub = it.sub.length ? '<ul>' + itemsOf(it.sub).map(s => `<li>${inline(s.text)}</li>`).join('\n') + '</ul>' : '';
      return `<dt${label === '常見陷阱' ? ' class="is-trap"' : ''}>${inline(label)}</dt><dd>${inline(rest)}${sub}</dd>`;
    });
    return `<dl class="qa${lead(ctx)}">\n${rows.join('\n')}\n</dl>`;
  },
  fails(node) {
    const items = itemsOf(node.lines).map(it => `<li><div>${inline(it.text)}</div></li>`);
    return (node.arg ? `<p class="fails-h">${inline(node.arg)}</p>\n` : '') + `<ul class="fails">\n${items.join('\n')}\n</ul>`;
  },
  terms(node) {
    const rows = itemsOf(node.lines).map(it => { const [k, v] = labelled(it.text) || [it.text, '']; return `<dt>${inline(k)}</dt><dd>${inline(v)}</dd>`; });
    return `<div class="ex-terms">\n<p class="ex-h">這一步的新名詞</p>\n<dl>\n${rows.join('\n')}\n</dl>\n</div>`;
  },
  todo(node) {
    const items = itemsOf(node.lines).map(it => {
      const m = it.text.match(/^`([^`]+)`[：:]?\s*(.*)$/);
      return m ? `<li><span class="f">${esc(m[1])}</span>${inline(m[2])}</li>` : `<li>${inline(it.text)}</li>`;
    });
    return `<div class="todo${lead({})}"><p class="todo-tag">${inline(node.arg || '待補')}</p><ul>\n${items.join('\n')}\n</ul></div>`;
  },
  system(node, ctx) {
    let boxes = 0;
    const gaps = [];  // arrow labels; an empty one gets a narrower column
    const out = [];
    let side = '';
    for (const raw of node.lines.map(l => l.trim()).filter(Boolean)) {
      if (raw.startsWith('→')) { gaps.push(raw.slice(1).trim()); out.push(`<li class="arch-link">${inline(raw.slice(1).trim())}</li>`); continue; }
      if (raw.startsWith('+')) { side = `<p class="arch-side">${inline(raw.slice(1).trim())}</p>`; continue; }
      const m = raw.match(/^(\*\*)?([^*：:]+)\1?[：:]\s*(.*)$/);
      if (!m) { warnings.push('系統圖看不懂這一行：' + raw); continue; }
      const [main, sub] = m[3].split('｜');
      boxes++;
      out.push(`<li class="arch-box${m[1] ? ' is-core' : ''}"><p class="arch-h">${inline(m[2])}</p><p class="arch-m">${inline(main)}${sub ? `<span class="arch-sub">${inline(sub)}</span>` : ''}</p></li>`);
    }
    const cols = Array.from({ length: boxes }, (_, k) => (k ? (gaps[k - 1] ? '76px ' : '40px ') : '') + 'minmax(0, 1fr)').join(' ');
    return `<figure class="figure arch${lead(ctx)}">\n<ol class="arch-sys" style="--cols: ${cols}">\n${out.join('\n')}\n</ol>${side}\n</figure>`;
  },
  states(node, ctx) {
    const out = [];
    let loop = '';
    for (const raw of node.lines.map(l => l.trim()).filter(Boolean)) {
      if (raw.startsWith('→')) { out.push(`<li class="tr">${inline(raw.slice(1).trim())}</li>`); continue; }
      if (raw.startsWith('↺')) { loop += (loop ? '<br>' : '') + inline(raw.slice(1).trim()); continue; }
      const alarm = /^\*\*.+?\*\*/.test(raw);
      const [name, outText] = raw.replace(/^\*\*(.+?)\*\*/, '$1').split('｜');
      out.push(`<li class="st${alarm ? ' is-alarm' : ''}"><p class="st-name">${inline(name.trim())}</p>${outText ? `<p class="st-out">${inline(outText.trim())}</p>` : ''}</li>`);
    }
    return `<ol class="states${lead(ctx)}">\n${out.join('\n')}\n</ol>` + (loop ? `\n<p class="st-loop">${loop}</p>` : '');
  },
  diagram(node, ctx) {
    const [title, id] = withId(node.arg);
    const file = id && path.join(figDir, id + '.html');
    if (file && fs.existsSync(file)) {
      const html = fs.readFileSync(file, 'utf8').trim();
      const cls = lead(ctx);
      return cls ? html.replace(/class="([^"]*)"/, (_, c) => `class="${c}${cls}"`) : html;
    }
    const want = `assets/handout/fig/${slug}/${id || '（加上 {#id}）'}.html`;
    if (!PREVIEW) problems.push(`圖還沒畫：${title} → ${want}`);
    return `<div class="todo${lead(ctx)}"><p class="todo-tag">圖待畫：${inline(title)}</p><ul><li>${inline(joinLines(node.lines))}</li><li><span class="f">${esc(want)}</span></li></ul></div>`;
  },
  step(node, ctx) {
    const [head, id0] = withId(node.arg);
    const [no, title] = head.split('｜').map(s => s.trim());
    const id = id0 || 'step' + (ctx.sec.steps.length + 1);
    const lines = [...node.lines];
    let tags = [], goal = '';
    // **標籤**： and **目標**： lines at the top
    while (lines.length && (!lines[0].trim() || labelled(lines[0]))) {
      const l = lines.shift();
      const kv = l.trim() && labelled(l);
      if (kv?.[0] === '標籤') tags = kv[1].split('、').map(s => s.trim()).filter(Boolean);
      else if (kv?.[0] === '目標') goal = kv[1];
      else if (kv) { lines.unshift(l); break; }
    }
    ctx.sec.steps.push({ id, no, title, kind: tags[0] || '' });
    const body = render(parseBlocks(lines), { ...ctx, step: true, nested: true });
    return `<article class="ex" id="${id}" aria-labelledby="${id}-h">\n<p class="ex-no">${esc(no)}</p>\n<h3 id="${id}-h">${inline(title || '')}</h3>\n` +
      (tags.length ? `<p class="ex-tags">${tags.map((t, k) => `<span${k ? '' : ' class="kind"'}>${inline(t)}</span>`).join('')}</p>\n` : '') +
      (goal ? `<p class="ex-goal"><b>目標</b>：${inline(goal)}</p>\n` : '') + body + '\n</article>';
  },
};

function render(nodes, ctx) {
  const out = [];
  for (const n of nodes) {
    switch (n.t) {
      case 'h':
        if (n.level === 3) { if (ctx.sec) ctx.sec.leadDone = true; out.push(`<h3${n.id ? ` id="${n.id}"` : ''}>${inline(n.text)}</h3>`); }
        else if (n.level === 4) out.push(ctx.step && !ctx.fold ? `<p class="ex-h">${inline(n.text)}</p>` : `<h4>${inline(n.text)}</h4>`);
        break;
      case 'p': out.push(paragraph(n, ctx)); break;
      case 'list': out.push(list(n, ctx)); break;
      case 'table': out.push(table(n, ctx)); break;
      case 'quote': out.push(quote(n)); break;
      case 'fence': out.push(fence(n)); break;
      case 'code':
        if (fs.existsSync(path.join(root, 'handout', 'code', n.file))) {
          out.push(`<!-- code:${n.file}${n.name ? ' name=' + n.name : ''} -->\n<!-- /code -->`);
        } else {
          if (!PREVIEW) problems.push('程式檔還沒寫：handout/code/' + n.file);
          out.push(`<div class="todo"><p class="todo-tag">程式待補</p><ul><li><span class="f">${esc(n.file)}</span></li></ul></div>`);
        }
        break;
      case 'html': out.push(n.html); break;
      case 'box':
        if (!BOX[n.name]) { warnings.push('不認得的區塊：' + n.name); break; }
        if (n.name === 'step' && ctx.sec && !ctx.sec.indexAt) {
          ctx.sec.indexAt = true;
          ctx.sec.indexLead = lead(ctx) !== '';
          out.push('@@STEP-INDEX@@');
        }
        out.push(BOX[n.name](n, ctx));
        break;
    }
  }
  return out.join('\n');
}

// ---------- page ----------

function frontmatter(src) {
  const m = src.match(/^---\n([\s\S]*?)\n---\n/);
  if (!m) throw new Error('缺少檔頭（--- 區塊）');
  const meta = {};
  let mapKey = null;
  for (const line of m[1].split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const nested = line.match(/^\s+([^:]+):\s*(.*)$/);
    if (nested && mapKey) { meta[mapKey][nested[1].trim()] = nested[2].trim(); continue; }
    const kv = line.match(/^([\w-]+):\s*(.*)$/);
    if (!kv) continue;
    const value = kv[2].replace(/\s+#.*$/, '').trim();
    if (value === '') { mapKey = kv[1]; meta[mapKey] = {}; } else { mapKey = null; meta[kv[1]] = value; }
  }
  return { meta, body: src.slice(m[0].length) };
}

const linkValue = v => { const m = v?.match(/^\[([^\]]+)\]\(([^)]+)\)$/); return m ? { label: m[1], href: m[2] } : null; };

function page(meta, body) {
  for (const k of ['type', 'title', 'lead', 'updated']) if (!meta[k]) problems.push('檔頭缺少 ' + k);
  if (meta.type && !TYPE_NAME[meta.type]) problems.push('不認得的 type：' + meta.type);
  if (meta.type === 'project' && !meta.scope) problems.push('專題要有 scope（學習用雛形的說明）');

  // split into sections at ##
  const all = parseBlocks(body.split('\n'));
  const sections = [];
  for (const n of all) {
    if (n.t === 'h' && n.level === 2) sections.push({ title: n.text, id: n.id, nodes: [] });
    else if (sections.length) sections.at(-1).nodes.push(n);
    else if (n.t !== 'html') warnings.push('第一個 ## 之前的內容會被略過');
  }
  if (meta.type === 'project' && !sections.some(s => s.title.includes('什麼情況下會失效'))) problems.push('專題要有「什麼情況下會失效」一節');

  const secHtml = sections.map((s, k) => {
    const id = s.id || 's' + (k + 1);
    const sec = { leadDone: false, steps: [], indexAt: false };
    let html = render(s.nodes, { sec });
    if (sec.steps.length) {
      const index = `<ol class="ex-index${sec.indexLead ? ' lead-in' : ''}">\n` + sec.steps.map(st =>
        `<li><a href="#${st.id}"><span class="n">${esc(st.no)}</span>${inline(st.title || '')}${st.kind ? `<span class="k">${esc(st.kind)}</span>` : ''}</a></li>`).join('\n') + '\n</ol>';
      html = html.replace('@@STEP-INDEX@@', index);
    }
    const no = String(k + 1).padStart(2, '0');
    return `<section class="sec" id="${id}" aria-labelledby="${id}-h">\n<p class="sec-no">${no}</p>\n<h2 id="${id}-h">${inline(s.title)}</h2>\n${html}\n</section>`;
  }).join('\n');

  const toc = sections.map((s, k) => `<li><a href="#${s.id || 's' + (k + 1)}"><span class="n">${String(k + 1).padStart(2, '0')}</span>${inline(s.title)}</a></li>`).join('\n');
  const version = meta.version || '';
  const here = meta.here || meta.title + (version ? '・' + version : '');
  const metaLine = meta.meta && typeof meta.meta === 'object'
    ? `\n<p class="meta">${Object.entries(meta.meta).map(([k, v]) => `<span><b>${esc(k)}</b>　${inline(v)}</span>`).join('')}</p>` : '';
  const sw = linkValue(meta.switch);
  const next = linkValue(meta.next);
  const imgs = usedImages.map(u => ({ ...u, c: credits.find(e => e.file === u.file) })).filter(u => u.c);
  const creditHtml = imgs.length ? `\n<footer class="credits"><h2>圖片來源</h2><ol>\n` + imgs.map(({ label, c }) =>
    `<li>${esc(label)}：<a href="${c.page}" target="_blank" rel="noopener">${esc(c.title.replace(/^File:/, ''))}</a>，${esc(c.author)}，<a href="${c.licenseUrl}" target="_blank" rel="noopener">${esc(c.license)}</a>${c.cropped ? '，經裁切' : ''}</li>`).join('\n') + '\n</ol></footer>' : '';

  return `<!doctype html>
<!-- 由 content/handout/${slug}.md 產生（node tools/md2html.mjs ${slug}），內容要改 md，不要直接改這個檔 -->
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(meta.title)}${version ? ' ' + esc(version) : ''}｜SkillLab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="../assets/handout.css">
</head>
<body class="hd">
<header class="topbar"><div class="topbar-in">
  <a class="brand" href="../index.html">SkillLab</a><span class="sep">/</span>
  <a href="../handout.html">講義</a><span class="sep">/</span>
  <span class="here">${inline(here)}</span>
</div></header>

<div class="page has-toc">
<header class="doc-head">
<p class="kicker" data-type="${meta.type}"><span class="type-tag">${esc(meta.tag || TYPE_NAME[meta.type] || '')}</span>${inline(version)}</p>
<h1>${inline(meta.title)}${meta.badge ? `<span class="badge">${esc(meta.badge)}</span>` : ''}</h1>
<p class="lead">${inline(meta.lead || '')}</p>${meta.scope ? `\n<p class="scope"><b>學習用的雛形</b>　${inline(meta.scope)}</p>` : ''}${metaLine}${sw ? `\n<a class="switch" href="${sw.href}">${esc(sw.label)}</a>` : ''}
</header>
<nav class="toc" aria-label="目錄">
<p class="toc-h">目錄</p>
<ol>
${toc}
</ol>
</nav>
<main class="doc">
${secHtml}
<nav class="doc-end" aria-label="下一步"><a class="back" href="../handout.html">← 講義選單</a>${next ? `<a href="${next.href}">${esc(next.label)} →</a>` : ''}</nav>${creditHtml}
</main>
</div>
<script src="../assets/handout.js"></script>
</body>
</html>
`;
}

// keep the menu card in step with the page: date, and 撰寫中 while the page has a badge
function syncMenu(meta) {
  const menuPath = path.join(root, 'handout.html');
  let menu = fs.readFileSync(menuPath, 'utf8');
  const href = `handout/${slug}.html`;
  let found = false;
  // each piece starts at one card and runs to the next card, so it holds that card's links and date
  menu = menu.split(/(?=<li class="card")/).map(card => {
    if (!card.startsWith('<li class="card"') || !card.includes(`href="${href}"`)) return card;
    found = true;
    const tag = card.match(/<p class="type-tag">([^<]*)<\/p>/)?.[1];
    if (tag && tag !== (meta.tag || TYPE_NAME[meta.type])) warnings.push(`選單卡片的類型標籤是「${tag}」，講義是「${meta.tag || TYPE_NAME[meta.type]}」`);
    const isLink = card.includes(`class="card-link" href="${href}"`);
    if (isLink) card = card.replace(/<time datetime="[^"]*">[^<]*<\/time>/, `<time datetime="${meta.updated}">${meta.updated}</time>`);
    return card.replace(new RegExp(`(<a class="ver" href="${href}">[^<]*?)(<span class="st">撰寫中</span>)?</a>`),
      (_, a) => `${a}${meta.badge ? '<span class="st">撰寫中</span>' : ''}</a>`);
  }).join('');
  if (!found) warnings.push('選單還沒有這份講義的卡片：照 CLAUDE.md 加一張，再跑一次');
  fs.writeFileSync(menuPath, menu);
}

// ---------- main ----------

const { meta, body } = frontmatter(fs.readFileSync(mdPath, 'utf8'));
const html = noBreak(page(meta, body));
for (const w of warnings) console.log('注意：' + w);
if (problems.length) {
  for (const p of [...new Set(problems)]) console.log('還不能上網頁：' + p);
  process.exit(1);
}
const outName = PREVIEW ? `_preview-${slug}.html` : `${slug}.html`;
fs.writeFileSync(path.join(root, 'handout', outName), html);
console.log('寫好 handout/' + outName);
execFileSync(process.execPath, [path.join(here, 'code-blocks.mjs')], { stdio: 'inherit' });
if (!PREVIEW) syncMenu(meta);
