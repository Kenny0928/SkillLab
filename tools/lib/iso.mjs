// Shared isometric drawing library.
// A scene is a function (iso) => svg inner markup. renderScene() calls it twice:
// pass 1 measures the bounding box (geometry + callout labels), pass 2 draws with the offset applied.

export const LBL = 38; // largest label size (phone) in drawing units; used for the bbox
const S = 0.8;
const K = Math.cos(Math.PI / 6);
const PAD = 24;

const pts = (a) => a.map((p) => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
export const poly = (cls, a) => `<polygon class="${cls}" points="${pts(a)}"/>`;
export const line = (cls, a, b) =>
  `<line class="${cls}" x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}"/>`;

const overlap = (a, b) => a.x0 < b.x1 - 0.5 && b.x0 < a.x1 - 0.5 && a.y0 < b.y1 - 0.5 && b.y0 < a.y1 - 0.5;
const centre = (b) => (b[0] + b[1] + b[2] + b[3] + b[4] + b[5]) / 2;

// rec = null: normal drawing. rec = a recorder (see recordScene): the same API, but P() also carries the
// world point (.w) and poly()/line() note their geometry, so a 3D renderer can rebuild the scene.
function createIso(rec = null) {
  const st = { OX: 0, OY: 0, bb: null };
  const items = [];
  const rects = [];
  const polyX = rec ? rec.poly : poly;
  const lineX = rec ? rec.line : line;

  // isometric projector: x->(x-y)cos30, y->(x+y)sin30 - z
  const P = (x, y, z) => {
    const X = (x - y) * K * S;
    const Y = ((x + y) * 0.5 - z) * S;
    const bb = st.bb;
    if (bb) {
      bb.x0 = Math.min(bb.x0, X); bb.x1 = Math.max(bb.x1, X);
      bb.y0 = Math.min(bb.y0, Y); bb.y1 = Math.max(bb.y1, Y);
    }
    const p = [X + st.OX, Y + st.OY];
    if (rec) p.w = [x, y, z];
    return p;
  };

  const screenBox = (b) => {
    const [x0, x1, y0, y1, z0, z1] = b;
    const xs = [], ys = [];
    for (const x of [x0, x1]) for (const y of [y0, y1]) for (const z of [z0, z1]) {
      const [X, Y] = P(x, y, z);
      xs.push(X); ys.push(Y);
    }
    return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
  };

  // back-to-front ordering of boxes
  function sortItems(list) {
    const n = list.length;
    const sb = list.map((it) => screenBox(it.box));
    const before = Array.from({ length: n }, () => new Set()); // before[j] has i => i drawn before j
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (!overlap(sb[i], sb[j])) continue;
        const a = list[i].box, b = list[j].box;
        const ib = a[1] <= b[0] || a[3] <= b[2] || a[5] <= b[4];
        const jb = b[1] <= a[0] || b[3] <= a[2] || b[5] <= a[4];
        if (ib && !jb) before[j].add(i);
        else if (jb && !ib) before[i].add(j);
        else if (centre(a) <= centre(b)) before[j].add(i);
        else before[i].add(j);
      }
    }
    const done = new Set();
    const out = [];
    while (out.length < n) {
      let pick = -1;
      for (let i = 0; i < n; i++) {
        if (done.has(i)) continue;
        if ([...before[i]].every((k) => done.has(k))) {
          if (pick < 0 || centre(list[i].box) < centre(list[pick].box)) pick = i;
        }
      }
      if (pick < 0) { // cycle: fall back to centre depth
        for (let i = 0; i < n; i++) {
          if (done.has(i)) continue;
          if (pick < 0 || centre(list[i].box) < centre(list[pick].box)) pick = i;
        }
        console.warn('cycle in depth order, fallback at', list[pick].part);
      }
      done.add(pick);
      out.push(list[pick]);
    }
    return out;
  }

  function boxSvg(b) {
    const [x0, x1, y0, y1, z0, z1] = b;
    const top = [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)];
    const right = [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)];
    const left = [P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)];
    return poly('f-left', left) + poly('f-right', right) + poly('f-top', top);
  }

  const attrs = (slot, part, loop) =>
    `data-slot="${slot}" data-part="${part}"` + (loop ? ' data-loop="1"' : '');

  const iso = {
    S, K, P, poly: polyX, line: lineX, pts, state: st,

    // a plain group (ground, flat shapes, network paths ...)
    group(slot, part, inner, loop = false) {
      if (rec) rec.assign(inner, slot, part, loop);
      return `<g ${attrs(slot, part, loop)}>${inner}</g>`;
    },

    // axis-aligned flat rectangle on the ground: [x0,x1,y0,y1]
    groundRect(cls, r, z = 0) {
      const [x0, x1, y0, y1] = r;
      return polyX(cls, [P(x0, y0, z), P(x1, y0, z), P(x1, y1, z), P(x0, y1, z)]);
    },
    groundLine(cls, a, b, z = 0) {
      return lineX(cls, P(a[0], a[1], z), P(b[0], b[1], z));
    },

    // box = [x0,x1,y0,y1,z0,z1]; decor() returns extra markup drawn inside the same group
    add(slot, part, box, decor = () => '', loop = false) {
      items.push({ slot, part, box, decor, loop });
    },
    // all boxes, back-to-front
    items() {
      return sortItems(items)
        .map((it) => `<g ${attrs(it.slot, it.part, it.loop)}>${boxSvg(it.box)}${rec ? rec.decorOf(it) : it.decor()}</g>`)
        .join('\n');
    },

    // dashed network path on the ground, arrowhead at the last point
    netPath(points) {
      const a = points.map(([x, y]) => P(x, y, 0.2));
      const d = 'M' + a.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
      const [ex, ey] = points[points.length - 1];
      const [px, py] = points[points.length - 2];
      let dx = ex - px, dy = ey - py;
      const L = Math.hypot(dx, dy); dx /= L; dy /= L;
      const nx = -dy, ny = dx;
      const len = 20, w = 7;
      const head = [P(ex, ey, 0.2), P(ex - dx * len + nx * w, ey - dy * len + ny * w, 0.2), P(ex - dx * len - nx * w, ey - dy * len - ny * w, 0.2)];
      return `<path class="net" d="${d}"/>` + polyX('net-head', head);
    },

    // callout: anchor `a` in world coords; `d` is the label point relative to the anchor, in drawing px
    // c = { slot, part, text, a:[x,y,z], d:[dx,dy], side:'l'|'r', loop? }
    callout(c) {
      const a = P(...c.a);
      const e = [a[0] + c.d[0], a[1] + c.d[1]];
      const tx = c.side === 'l' ? e[0] - 10 : e[0] + 10;
      const anchor = c.side === 'l' ? 'end' : 'start';
      const w = [...c.text].reduce((s, ch) => s + (ch.charCodeAt(0) > 255 ? LBL : LBL * 0.6), 0);
      const x0 = c.side === 'l' ? tx - w : tx;
      const r = { slot: c.slot, loop: !!c.loop, name: c.text, x0, x1: x0 + w, y0: e[1] - LBL * 0.55, y1: e[1] + LBL * 0.55, lead: [a, e] };
      rects.push(r);
      if (st.bb) {
        const bb = st.bb;
        bb.x0 = Math.min(bb.x0, r.x0); bb.x1 = Math.max(bb.x1, r.x1);
        bb.y0 = Math.min(bb.y0, r.y0); bb.y1 = Math.max(bb.y1, r.y1);
      }
      return (
        `<g class="callout" ${attrs(c.slot, c.part, c.loop)}>` +
        lineX('lead', a, e) +
        `<circle class="dot" cx="${a[0].toFixed(1)}" cy="${a[1].toFixed(1)}" r="5"/>` +
        `<text class="lbl" x="${tx.toFixed(1)}" y="${e[1].toFixed(1)}" text-anchor="${anchor}" dominant-baseline="central">${c.text}</text>` +
        `</g>`
      );
    },
    callouts(list) {
      return list.map((c) => iso.callout(c)).join('\n');
    },

    _items: items,
    _rects: rects,
    screenBox,
  };
  return iso;
}

// Draws a scene and computes its viewBox. Returns { w, h, inner, warnings }.
export function renderScene(scene) {
  const m = createIso();
  m.state.bb = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
  scene(m);
  const box = m.state.bb;

  const iso = createIso();
  iso.state.OX = PAD - box.x0;
  iso.state.OY = PAD - box.y0;
  const w = Math.round(box.x1 - box.x0 + 2 * PAD);
  const h = Math.round(box.y1 - box.y0 + 2 * PAD);
  const inner = scene(iso);

  // label collision check: label rects vs projected boxes, and vs each other
  // within the same step group (a slot, or the loop group shown together at the last step)
  const warnings = [];
  const hit = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  const rects = iso._rects;
  for (const r of rects) {
    if (r.x0 < 0 || r.y0 < 0 || r.x1 > w || r.y1 > h) warnings.push(r.name + ' outside viewBox');
    for (const it of iso._items) if (hit(r, iso.screenBox(it.box))) warnings.push(r.name + ' ~ bbox of ' + it.part);
    for (const o of rects) {
      if (o === r || o.name >= r.name) continue;
      // labels shown together need breathing room, not just zero overlap
      const g = 10, ro = { x0: o.x0 - g, x1: o.x1 + g, y0: o.y0 - g, y1: o.y1 + g };
      if (o.slot === r.slot || (o.loop && r.loop)) if (hit(r, ro)) warnings.push(r.name + ' too close to ' + o.name);
    }
  }
  // leader lines shown together must not cross each other or run through another label
  const cross = (p1, p2, p3, p4) => {
    const d = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    return d(p1, p2, p3) * d(p1, p2, p4) < 0 && d(p3, p4, p1) * d(p3, p4, p2) < 0;
  };
  const segHitsRect = (p, q, b) => {
    for (let t = 0; t <= 1; t += 0.02) {
      const x = p[0] + (q[0] - p[0]) * t, y = p[1] + (q[1] - p[1]) * t;
      if (x > b.x0 && x < b.x1 && y > b.y0 && y < b.y1) return true;
    }
    return false;
  };
  for (const r of rects) for (const o of rects) {
    if (o === r || !(o.slot === r.slot || (o.loop && r.loop))) continue;
    if (o.name < r.name && cross(r.lead[0], r.lead[1], o.lead[0], o.lead[1])) warnings.push(r.name + ' leader crosses ' + o.name);
    if (segHitsRect(r.lead[0], r.lead[1], o)) warnings.push(r.name + ' leader runs through label ' + o.name);
  }
  return { w, h, inner, warnings, rects, OX: iso.state.OX, OY: iso.state.OY };
}

// ---------- record mode: the same drawing, kept as 3D geometry for the Blender pipeline ----------
// What a record-mode iso notes down: every box from iso.add(), and every poly()/line() whose points all came
// from P() (those carry their world point as .w). Raw markup the scene writes itself (text, dashed paths,
// shadows) is not recorded. Ids are shared by polys and lines; they are what data-pid in the markup carries.
function createRecorder() {
  const prims = [];
  const boxes = [];
  const boxIndex = new Map();
  let owner = null; // { slot, part, loop, host } while an item's decor() runs
  const note = (kind, fields) => {
    const o = owner;
    const id = prims.length;
    prims.push({
      id, kind, ...fields,
      slot: o ? o.slot : null, part: o ? o.part : null, loop: o ? o.loop : null, host: o ? o.host : null,
    });
    return id;
  };
  const tag = (markup, id) => markup.replace(/\/>$/, ` data-pid="${id}"/>`);
  return {
    poly(cls, a) {
      const m = poly(cls, a);
      return a.every((p) => p.w) ? tag(m, note('poly', { cls, pts: a.map((p) => p.w) })) : m;
    },
    line(cls, a, b) {
      const m = line(cls, a, b);
      return a.w && b.w ? tag(m, note('line', { cls, a: a.w, b: b.w })) : m;
    },
    // iso.group(): everything drawn inside belongs to this slot/part, unless an item already claimed it
    assign(inner, slot, part, loop) {
      for (const [, id] of inner.matchAll(/data-pid="(\d+)"/g)) {
        const p = prims[+id];
        if (p.slot === null) { p.slot = slot; p.part = part; p.loop = !!loop; }
      }
    },
    // iso.items(): record the item's box, then run its decor() with the item as owner of what it draws
    decorOf(it) {
      if (!boxIndex.has(it)) {
        boxIndex.set(it, boxes.length);
        boxes.push({ kind: 'box', slot: it.slot, part: it.part, loop: !!it.loop, box: it.box });
      }
      owner = { slot: it.slot, part: it.part, loop: !!it.loop, host: boxIndex.get(it) };
      try { return it.decor(); } finally { owner = null; }
    },
    result() {
      for (const p of prims) if (p.slot === null) { p.slot = 'base'; p.loop = false; }
      return {
        boxes,
        polys: prims.filter((p) => p.kind === 'poly'),
        lines: prims.filter((p) => p.kind === 'line'),
      };
    },
  };
}

// Runs the scene once more in record mode (same offsets as the final drawing, so the 3D geometry is in the
// same world units as the SVG). Returns { w, h, OX, OY, S, boxes, polys, lines }, all in world coordinates:
// a world point (x,y,z) is drawn at ((x-y)*K*S + OX, ((x+y)/2 - z)*S + OY), K = cos 30deg.
// poly/line carry { id, cls, slot, part, loop, host } (host = index into boxes of the box whose decor() drew it, else null).
export function recordScene(scene) {
  const { w, h, OX, OY } = renderScene(scene);
  const rec = createRecorder();
  const iso = createIso(rec);
  iso.state.OX = OX;
  iso.state.OY = OY;
  scene(iso);
  return { w, h, OX, OY, S, ...rec.result() };
}
