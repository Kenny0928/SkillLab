// Copies the example source files in handout/code/ into the handout pages, so the page always
// shows the code that was compiled/tested, and colours every code block. Run after editing any
// file in handout/code/ or any terminal block in a page:
//   node tools/code-blocks.mjs
// In the HTML, a file block is written as
//   <!-- code:python/gmail_alert.py -->  …anything…  <!-- /code -->
// optional display name:  <!-- code:python/config.example.json name=config.json -->
// A hand-written block (terminal commands) is written as <code data-lang="sh">…</code>;
// every <code data-lang="…"> on the page is re-coloured from its text, so editing the
// commands and re-running this script is enough.
//
// Colour classes (see .code .c/.k/.s/.n/.f/.t/.a in assets/handout.css):
//   c comment · k keyword · s string · n number / constant · f function · t type · a JSON key
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const pagesDir = path.join(root, 'handout');
const codeDir = path.join(pagesDir, 'code');

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const unesc = s => s.replace(/<[^>]*>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
const span = (cls, s) => cls ? `<span class="${cls}">${esc(s)}</span>` : esc(s);
const words = s => new Set(s.split(' '));

const LANG = {
  py: {
    kw: words('and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield'),
    types: words('bool bytes dict float int list object set str tuple'),
    consts: words('True False None'),
  },
  ino: {
    kw: words('break case class const continue default delete do else enum for goto if inline new return sizeof static struct switch typedef union volatile while'),
    types: words('void bool boolean byte char double float int long short signed unsigned word size_t String int8_t int16_t int32_t uint8_t uint16_t uint32_t'),
    consts: words('true false nullptr'),
  },
  js: {
    kw: words('async await break case catch class const continue default delete do else export extends finally for function if import in instanceof let new of return switch this throw try typeof var void while yield'),
    types: new Set(),
    consts: words('true false null undefined'),
  },
  json: { kw: new Set(), types: new Set(), consts: words('true false null') },
};

// Index just past the string literal that starts at i (quote char at i).
// Python triple quotes and JS `template` strings may span lines.
function stringEnd(src, i, triple) {
  const q = triple ? src.substr(i, 3) : src[i];
  const multiline = triple || q === '`';
  let j = i + q.length;
  while (j < src.length) {
    if (src[j] === '\\') { j += 2; continue; }
    if (src.startsWith(q, j)) return j + q.length;
    if (!multiline && src[j] === '\n') return j;
    j++;
  }
  return src.length;
}

// f"…{expr}…": the literal parts are strings, the expressions inside {} stay plain.
function fString(text) {
  let out = '', lit = '', i = 0;
  while (i < text.length) {
    if (text.startsWith('{{', i) || text.startsWith('}}', i)) { lit += text.substr(i, 2); i += 2; continue; }
    if (text[i] !== '{') { lit += text[i++]; continue; }
    let depth = 1, j = i + 1;
    while (j < text.length && depth) { if (text[j] === '{') depth++; else if (text[j] === '}') depth--; j++; }
    out += span('s', lit + '{') + esc(text.slice(i + 1, j - 1));
    lit = '}';
    i = j;
  }
  return out + span('s', lit);
}

function identClass(w, L, after, prev) {
  if (L.consts.has(w)) return 'n';
  if (L.kw.has(w)) return 'k';
  if (L.types.has(w)) return 't';
  if (prev === 'def') return 'f';
  if (prev === 'class') return 't';
  const bare = w.replace(/^_+/, '');
  if (/^[A-Z]/.test(bare) && /[a-z]/.test(bare)) return 't'; // Serial, Path, EmailMessage
  if (/^\s*\(/.test(after)) return 'f';                     // calls and definitions, F(), SMTP_SSL()
  if (/^[A-Z][A-Z0-9_]+$/.test(bare)) return 'n';          // HIGH, A0, LDR_PIN, CONFIG_PATH
  return '';
}

const ID = /[A-Za-z_]\w*/y;
const JS_ID = /[A-Za-z_$][\w$]*/y;
const NUM = /(?:0[xX][\da-fA-F]+|0[bB][01]+|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?)[uUlLfFjJ]*/y;

function highlightCode(src, lang) {
  const L = LANG[lang];
  const isPy = lang === 'py', isC = lang === 'ino', isJs = lang === 'js', isJson = lang === 'json';
  const slashComments = isC || isJs;
  const id = isJs ? JS_ID : ID;
  let out = '', i = 0, prev = '', lineStart = true;
  const n = src.length;
  while (i < n) {
    const ch = src[i];
    if (ch === '\n') { out += ch; i++; lineStart = true; continue; }
    if (ch === ' ' || ch === '\t') { out += ch; i++; continue; }
    const atLineStart = lineStart;
    lineStart = false;
    // comments
    if ((isPy && ch === '#') || (slashComments && src.startsWith('//', i))) {
      let j = src.indexOf('\n', i);
      if (j === -1) j = n;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    if (slashComments && src.startsWith('/*', i)) {
      let j = src.indexOf('*/', i + 2);
      j = j === -1 ? n : j + 2;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    // #include / #define, @decorator
    if ((isC && ch === '#' && atLineStart) || (isPy && ch === '@' && atLineStart)) {
      const m = (isC ? /#\s*\w+/y : /@[A-Za-z_][\w.]*/y);
      m.lastIndex = i;
      const hit = m.exec(src);
      if (hit) { out += span('k', hit[0]); i += hit[0].length; prev = hit[0]; continue; }
    }
    // strings
    if (ch === '"' || ch === "'" || (isJs && ch === '`')) {
      const triple = isPy && src.startsWith(ch.repeat(3), i);
      const j = stringEnd(src, i, triple);
      const text = src.slice(i, j);
      const isKey = isJson && /^\s*:/.test(src.slice(j, j + 20));
      // a Python string holding a whole web page (dashboard.py) is coloured as HTML
      if (triple && text.length >= 6 && text.endsWith(ch.repeat(3)) && /^\s*<(!doctype|html)/i.test(text.slice(3))) {
        out += span('s', text.slice(0, 3)) + highlightHtml(text.slice(3, -3)) + span('s', text.slice(-3));
      } else {
        out += span(isKey ? 'a' : 's', text);
      }
      prev = '"'; i = j; continue;
    }
    // numbers
    if (/\d/.test(ch) || (ch === '.' && /\d/.test(src[i + 1] || ''))) {
      NUM.lastIndex = i;
      const m = NUM.exec(src);
      if (m) { out += span('n', m[0]); i += m[0].length; prev = m[0]; continue; }
    }
    // words
    id.lastIndex = i;
    const m = id.exec(src);
    if (m) {
      const w = m[0];
      const q = src[i + w.length];
      // Python string prefixes: f"…", r'…', b"…", rb"…"
      if (isPy && (q === '"' || q === "'") && /^(?:[rRbBuUfF]|[rR][bBfF]|[bBfF][rR])$/.test(w)) {
        const s = i + w.length;
        const j = stringEnd(src, s, src.startsWith(q.repeat(3), s));
        const text = src.slice(i, j);
        out += /f/i.test(w) ? fString(text) : span('s', text);
        prev = '"'; i = j; continue;
      }
      out += span(identClass(w, L, src.slice(i + w.length, i + w.length + 40), prev), w);
      prev = w; i += w.length; continue;
    }
    out += esc(ch);
    if (ch !== '.') prev = ch;
    i++;
  }
  return out;
}

// HTML: tag names, attribute names and values; <style> as CSS, <script> as JS.
function highlightHtml(src) {
  let out = '', i = 0;
  const n = src.length;
  const TAG = /<(\/?)([A-Za-z!][\w-]*)/y;
  const ATTR = /(\s+)|([^\s=>"']+)(?:(\s*=\s*)("[^"]*"|'[^']*'|[^\s>"']+))?|([\s\S])/gy;
  while (i < n) {
    if (src.startsWith('<!--', i)) {
      let j = src.indexOf('-->', i);
      j = j === -1 ? n : j + 3;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    TAG.lastIndex = i;
    const t = src[i] === '<' && TAG.exec(src);
    if (!t) {
      let j = src.indexOf('<', i + 1);
      if (j === -1) j = n;
      out += esc(src.slice(i, j)); i = j; continue;
    }
    out += esc('<' + t[1]) + span('k', t[2]);
    i += t[0].length;
    let end = src.indexOf('>', i);
    if (end === -1) end = n;
    const attrs = src.slice(i, end);
    ATTR.lastIndex = 0;
    let a;
    while (ATTR.lastIndex < attrs.length && (a = ATTR.exec(attrs))) {
      const [, ws, name, eq, val, other] = a;
      out += ws ? ws : name ? span('a', name) + esc(eq || '') + (val ? span('s', val) : '') : esc(other);
    }
    out += esc(src.slice(end, end + 1));
    i = end + 1;
    const tag = t[2].toLowerCase();
    if (!t[1] && (tag === 'style' || tag === 'script')) {
      let close = src.toLowerCase().indexOf(`</${tag}`, i);
      if (close === -1) close = n;
      const inner = src.slice(i, close);
      out += tag === 'style' ? highlightCss(inner) : highlightCode(inner, 'js');
      i = close;
    }
  }
  return out;
}

// CSS: selectors, property names, and numbers / colours / !important in values.
function highlightCss(src) {
  const VALUE = /(\s+)|("[^"]*"|'[^']*')|(!important)|(#[\da-fA-F]{3,8})(?![\w-])|(-?(?:\d+\.?\d*|\.\d+)[a-zA-Z%]*)|([A-Za-z_-][\w-]*)(?=\()|([A-Za-z_-][\w-]*)|([\s\S])/gy;
  const value = v => {
    let out = '', m;
    VALUE.lastIndex = 0;
    while (VALUE.lastIndex < v.length && (m = VALUE.exec(v))) {
      const [all, ws, str, imp, hex, num, fn] = m;
      out += ws ? ws : str ? span('s', str) : imp ? span('k', imp) : hex || num ? span('n', all) : fn ? span('f', fn) : esc(all);
    }
    return out;
  };
  const keepSpace = (seg, cls) => {
    const [, lead, body, tail] = /^(\s*)([\s\S]*?)(\s*)$/.exec(seg);
    return lead + span(cls, body) + tail;
  };
  let out = '', i = 0, depth = 0;
  const n = src.length;
  while (i < n) {
    if (src.startsWith('/*', i)) {
      let j = src.indexOf('*/', i + 2);
      j = j === -1 ? n : j + 2;
      out += span('c', src.slice(i, j)); i = j; continue;
    }
    let j = i;
    while (j < n && !'{};'.includes(src[j]) && !src.startsWith('/*', j)) {
      j = src[j] === '"' || src[j] === "'" ? stringEnd(src, j, false) : j + 1;
    }
    const seg = src.slice(i, j);
    const delim = src[j];
    const colon = seg.indexOf(':');
    if (delim === '{') out += seg.trim() ? keepSpace(seg, seg.trim()[0] === '@' ? 'k' : 't') : seg;
    else if (depth > 0 && colon > 0 && seg.slice(0, colon).trim()) {
      out += keepSpace(seg.slice(0, colon), 'a') + ':' + value(seg.slice(colon + 1));
    } else out += esc(seg);
    if (delim === '{' || delim === '}' || delim === ';') {
      out += delim;
      depth = Math.max(0, depth + (delim === '{') - (delim === '}'));
      j++;
    }
    i = j;
  }
  return out;
}

// Terminal commands: the command word, -options and $VARIABLES are coloured.
function highlightShell(src) {
  return src.split('\n').map(line => {
    let out = '', expectCmd = true;
    const TOK = /(\s+)|("(?:\\.|[^"\\])*"?|'[^']*'?)|(#.*$)|(&&|\|\||[|;])|([^\s"'|;&]+)/gy;
    let m;
    while ((m = TOK.exec(line))) {
      const [all, ws, str, comment, op, word] = m;
      if (ws) out += ws;
      else if (str) out += span('s', str);
      else if (comment) out += span('c', comment);
      else if (op) { out += esc(op); expectCmd = true; }
      else if (word) {
        if (expectCmd && word === 'sudo') out += span('k', word);
        else if (expectCmd) { out += span('f', word); expectCmd = false; }
        else if (/^--?[A-Za-z]/.test(word)) out += span('n', word);
        else if (/^\$\w+$/.test(word)) out += span('t', word);
        else out += esc(word);
      } else out += esc(all);
    }
    return out;
  }).join('\n');
}

function highlight(src, lang) {
  if (lang === 'sh') return highlightShell(src);
  if (LANG[lang]) return highlightCode(src, lang);
  return esc(src);
}

function block(rel, name) {
  const file = path.join(codeDir, rel);
  const src = fs.readFileSync(file, 'utf8').replace(/\s+$/, '') + '\n';
  const ext = path.extname(rel).slice(1);
  const lang = ext === 'py' ? 'py' : ext === 'ino' ? 'ino' : ext === 'json' ? 'json' : 'plain';
  const label = name || path.basename(rel);
  return `<div class="code" data-lang="${lang}">\n` +
    `<div class="code-bar"><span><span class="code-name">${esc(label)}</span>` +
    `<span class="code-lines">${src.split('\n').length - 1} 行</span></span>` +
    `<button class="copy" type="button" aria-label="複製 ${esc(label)}">複製</button></div>\n` +
    `<pre tabindex="0"><code data-lang="${lang}">${esc(src)}</code></pre>\n</div>`;
}

let total = 0, coloured = 0, bare = 0;
for (const f of fs.readdirSync(pagesDir).filter(f => f.endsWith('.html'))) {
  const p = path.join(pagesDir, f);
  const html = fs.readFileSync(p, 'utf8');
  let count = 0;
  let next = html.replace(
    /<!-- code:([^\s>]+)((?: [a-z]+=[^\s>]+)*) -->[\s\S]*?<!-- \/code -->/g,
    (_, rel, attrs) => {
      count++;
      const name = (attrs.match(/ name=([^\s>]+)/) || [])[1];
      return `<!-- code:${rel}${attrs} -->\n${block(rel, name)}\n<!-- /code -->`;
    });
  next = next.replace(/<code data-lang="(\w+)">([\s\S]*?)<\/code>/g, (_, lang, body) => {
    coloured++;
    return `<code data-lang="${lang}">${highlight(unesc(body), lang)}</code>`;
  });
  const missing = (next.match(/<pre[^>]*><code>/g) || []).length;
  if (missing) console.log(`${f}: ${missing} code blocks have no data-lang and stay uncoloured`);
  bare += missing;
  if (next !== html) fs.writeFileSync(p, next);
  if (count) console.log(`${f}: ${count} source files`);
  total += count;
}
console.log(`${coloured} blocks coloured`);
if (!total && !coloured) console.log('no code markers found');
