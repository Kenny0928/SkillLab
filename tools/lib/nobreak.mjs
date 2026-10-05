// Keeps names and quantities on one line (CLAUDE.md: 產品名稱不斷行):
//   ESP32-CAM, Wi-Fi, micro-USB → <span class="nw">…</span> (browsers break after a hyphen)
//   5 MB, 240 MHz              → number&nbsp;unit
//   微專題 02                   → 微專題&nbsp;02
// Only text between tags is touched; svg, pre, code, script, style and title are skipped,
// and running it twice changes nothing.
const UNITS = 'KB|MB|GB|TB|MHz|GHz|kHz|Hz|ms|µs|cm|mm|m|kΩ|Ω|V|mA|A|fps|TOPS';
const UNIT_RE = new RegExp(`(\\d) (${UNITS})(?![A-Za-z0-9])`, 'g');
const HYPHEN_RE = /(^|[^\w/.-])([A-Za-z0-9]+(?:-[A-Za-z0-9]+)+)(?![\w/.-])/g;
const SKIP = /^<(\/?)(svg|pre|code|script|style|title)\b/i;

export function noBreak(html) {
  let skip = 0;
  let prev = '';
  return html.split(/(<[^>]+>)/).map(part => {
    const before = prev;
    prev = part;
    if (part.startsWith('<')) {
      const m = part.match(SKIP);
      if (m && !part.endsWith('/>')) skip = Math.max(0, skip + (m[1] ? -1 : 1));
      return part;
    }
    if (skip > 0 || !part.trim()) return part;
    let t = part.replace(UNIT_RE, '$1&nbsp;$2').replace(/微專題 (\d\d)/g, '微專題&nbsp;$1');
    if (before !== '<span class="nw">') t = t.replace(HYPHEN_RE, '$1<span class="nw">$2</span>');
    return t;
  }).join('');
}
