// Example: camera drone.
// PLACEHOLDER SCENE: one small box per slot. To be replaced wholesale by the real drawing.

const LOOP_LABELS = new Set(['IMU', '飛控板', '電子調速器', '馬達']);

function scene(iso) {
  const { poly, line } = iso;
  // whole scene is drawn in a 320-centred model and scaled up by SC
  const SC = 1.3, MID = 320;
  const tx = (v) => MID + (v - MID) * SC;
  const P = (x, y, z) => iso.P(tx(x), tx(y), z * SC);
  const add = (slot, part, b, decor) =>
    iso.add(slot, part, [tx(b[0]), tx(b[1]), tx(b[2]), tx(b[3]), b[4] * SC, b[5] * SC], decor, LOOP_LABELS.has(part));

  // ---------- layout (world units) ----------
  const CX = 320, CY = 320;
  const GROUND = [150, 490, 150, 490];
  const PAD = [250, 390, 250, 390];
  const PAD_IN = [262, 378, 262, 378];
  const BODY = [270, 370, 270, 370, 190, 210];
  const TIP = 140;           // arm length from the centre to a motor
  const BLADE = 100;         // propeller radius (neighbouring discs nearly touch)

  const circle = (cx, cy, z, r, n = 40) => {
    const a = [];
    for (let i = 0; i < n; i++) {
      const t = (i / n) * Math.PI * 2;
      a.push(P(cx + r * Math.cos(t), cy + r * Math.sin(t), z));
    }
    return a;
  };
  const ring = (cx, cy, z, r) => {
    const a = circle(cx, cy, z, r);
    return `<path class="cone" fill="none" d="M${a.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L')} Z"/>`;
  };

  // ---------- base: ground, pad, soft shadow ----------
  const out = [];
  const [gx0, gx1, gy0, gy1] = GROUND;
  const slab =
    poly('f-left', [P(gx0, gy1, 0), P(gx1, gy1, 0), P(gx1, gy1, -12), P(gx0, gy1, -12)]) +
    poly('f-right', [P(gx1, gy0, 0), P(gx1, gy1, 0), P(gx1, gy1, -12), P(gx1, gy0, -12)]);
  const sh = (a) => `<polygon style="fill:#efede8;stroke:none" points="${iso.pts(a)}"/>`;
  const shadow = [sh([P(268, 268, 0.1), P(372, 268, 0.1), P(372, 372, 0.1), P(268, 372, 0.1)])];
  for (const [dx, dy] of [[TIP, 0], [-TIP, 0], [0, TIP], [0, -TIP]]) {
    shadow.push(sh(circle(CX + dx, CY + dy, 0.1, 46)));
  }
  out.push(iso.group('base', 'ground',
    iso.groundRect('ground', GROUND.map(tx)) + slab +
    iso.groundRect('ground', PAD.map(tx)) +
    iso.groundRect('ground', PAD_IN.map(tx)) +
    shadow.join('')));

  // ---------- low landing gear (base): two skids on short struts ----------
  for (const x of [280, 354]) {
    add('base', 'skid', [x, x + 8, 262, 378, 150, 156]);
    add('base', 'strut', [x + 1, x + 7, 272, 278, 156, 190]);
    add('base', 'strut', [x + 1, x + 7, 352, 358, 156, 190]);
  }

  // ---------- body, exploded ----------
  add('base', 'body', BODY, () => {
    const y = BODY[3] + 0.3, x = BODY[1] + 0.3;
    return line('detail', P(276, y, 200), P(364, y, 200)) + line('detail', P(x, 276, 200), P(x, 364, 200));
  });
  // 電子調速器 (4-in-1 ESC) floating above the body
  add('act', '電子調速器', [276, 364, 276, 364, 222, 228], () => {
    const out2 = [];
    for (const [cx, cy] of [[286, 286], [354, 286], [286, 354], [354, 354]]) {
      out2.push(poly('screen', [P(cx - 5, cy - 5, 228.3), P(cx + 5, cy - 5, 228.3), P(cx + 5, cy + 5, 228.3), P(cx - 5, cy + 5, 228.3)]));
    }
    return out2.join('');
  });
  // 飛控板
  add('decide', '飛控板', [290, 350, 290, 350, 244, 250], () => {
    const y = 350.3;
    return line('detail', P(296, y, 247), P(344, y, 247)) +
      line('detail', P(294, 296, 250.3), P(294, 344, 250.3));
  });
  // IMU, 氣壓計 on the flight controller
  add('sense', 'IMU', [300, 320, 322, 344, 250, 260]);
  add('sense', '氣壓計', [326, 344, 300, 318, 250, 258], () => {
    const x = 344.3;
    return line('detail', P(x, 305, 254), P(x, 313, 254));
  });
  // 記憶卡 sticking out of the body's side slot
  add('record', '記憶卡', [370, 436, 262, 296, 196, 205], () =>
    line('detail', P(378, 268, 205.3), P(378, 290, 205.3)));

  // ---------- lifted top shell, mast, compass, GPS ----------
  add('base', 'shell', [266, 374, 266, 374, 326, 333], () => {
    const out2 = [];
    for (const [x, y] of [[266, 266], [374, 266], [374, 374], [266, 374]]) {
      out2.push(line('cone', P(x, y, 326), P(x, y, 210)));
    }
    return out2.join('');
  });
  add('base', 'mast', [314, 326, 314, 326, 333, 343]);
  add('sense', '指南針', [308, 332, 308, 332, 343, 357], () =>
    poly('screen', [P(314, 332.3, 346), P(326, 332.3, 346), P(326, 332.3, 354), P(314, 332.3, 354)]));
  add('base', 'mast', [314, 326, 314, 326, 357, 367]);
  add('sense', 'GPS', [300, 340, 300, 340, 367, 378], () =>
    line('detail', P(306, 340.3, 372), P(334, 340.3, 372)));

  // ---------- arms, motors (on the arm tips), propellers (perpendicular to the arm) ----------
  const arms = [
    { arm: [CX + 50, CX + TIP, CY - 5, CY + 5], c: [CX + TIP, CY], along: 'x' },
    { arm: [CX - TIP, CX - 50, CY - 5, CY + 5], c: [CX - TIP, CY], along: 'x' },
    { arm: [CX - 5, CX + 5, CY + 50, CY + TIP], c: [CX, CY + TIP], along: 'y' },
    { arm: [CX - 5, CX + 5, CY - TIP, CY - 50], c: [CX, CY - TIP], along: 'y' },
  ];
  const ANGLES = [20, 70, 115, 160];
  for (const [k, { arm, c }] of arms.entries()) {
    add('base', 'arm', [arm[0], arm[1], arm[2], arm[3], 196, 204]);
    add('act', '馬達', [c[0] - 20, c[0] + 20, c[1] - 20, c[1] + 20, 204, 224]);
    // flat 2-blade bar, each one stopped at its own angle, inside the dashed disc
    const th = (ANGLES[k] * Math.PI) / 180;
    const blade = () => {
      const L = BLADE * 0.8, w = 6, z = 236;
      const ux = Math.cos(th), uy = Math.sin(th), vx = -uy, vy = ux;
      return poly('f-top', [
        P(c[0] + ux * L + vx * w, c[1] + uy * L + vy * w, z), P(c[0] + ux * L - vx * w, c[1] + uy * L - vy * w, z),
        P(c[0] - ux * L - vx * w, c[1] - uy * L - vy * w, z), P(c[0] - ux * L + vx * w, c[1] - uy * L + vy * w, z),
      ]) + ring(c[0], c[1], 236, BLADE);
    };
    add('act', '螺旋槳', [c[0] - 4, c[0] + 4, c[1] - 4, c[1] + 4, 224, 235], blade);
  }

  // ---------- below the body: gimbal + camera, 圖傳 ----------
  add('sense', '相機', [312, 328, 362, 374, 186, 190]);
  add('sense', '相機', [300, 340, 366, 400, 158, 186], () =>
    poly('screen', [P(310, 400.3, 164), P(330, 400.3, 164), P(330, 400.3, 180), P(310, 400.3, 180)]));
  add('send', '圖傳', [272, 296, 370, 384, 184, 204]);
  add('send', '圖傳', [282, 287, 375, 380, 204, 242]);

  // ---------- remote controller, front-left on the slab ----------
  add('send', '遙控器', [165, 245, 435, 485, 0, 14], () => {
    const z = 14.3;
    return poly('screen', [P(197, 458, z), P(211, 458, z), P(211, 466, z), P(197, 466, z)]);
  });
  add('send', '遙控器', [177, 187, 452, 462, 14, 22]);
  add('send', '遙控器', [223, 233, 452, 462, 14, 22]);
  add('send', '遙控器', [172, 177, 437, 442, 14, 80]);
  add('send', '遙控器', [233, 238, 437, 442, 14, 80]);

  // ---------- network paths (send) ----------
  const route = (pts) => {
    const a = pts.map(([x, y, z]) => P(x, y, z));
    const d = 'M' + a.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
    const [p, q] = [a[a.length - 2], a[a.length - 1]];
    let dx = q[0] - p[0], dy = q[1] - p[1];
    const L = Math.hypot(dx, dy); dx /= L; dy /= L;
    const nx = -dy, ny = dx, len = 20, w = 7;
    const head = [q, [q[0] - dx * len + nx * w, q[1] - dy * len + ny * w], [q[0] - dx * len - nx * w, q[1] - dy * len - ny * w]];
    return `<path class="net" d="${d}"/>` + poly('net-head', head);
  };
  out.push(iso.items());
  out.push(iso.group('send', 'network',
    route([[250, 478, 0.2], [292, 478, 0.2], [292, 392, 0.2], [292, 392, 170]]) +
    route([[278, 392, 170], [278, 392, 0.2], [278, 462, 0.2], [252, 462, 0.2]])));


  // ---------- callouts ----------
  const c = (slot, text, a, d, side) => ({ slot, part: text, text, a: [tx(a[0]), tx(a[1]), a[2] * SC], d, side, loop: LOOP_LABELS.has(text) });
  out.push(iso.callouts([
    c('sense', 'GPS', [320, 320, 378], [60, -70], 'r'),
    c('sense', '指南針', [320, 332, 350], [-170, -90], 'l'),
    c('sense', 'IMU', [310, 344, 260], [-190, -30], 'l'),
    c('sense', '氣壓計', [344, 309, 258], [230, -5], 'r'),
    c('sense', '相機', [320, 400, 172], [130, 110], 'r'),
    c('decide', '飛控板', [330, 350, 250], [-240, 60], 'l'),
    c('act', '電子調速器', [364, 330, 225], [200, -50], 'r'),
    c('act', '螺旋槳', [CX + TIP + 75, CY + 27, 236], [120, 10], 'r'),
    c('act', '馬達', [CX + TIP + 20, CY + 10, 214], [140, 110], 'r'),
    c('record', '記憶卡', [430, 280, 205], [130, -130], 'r'),
    c('send', '遙控器', [205, 460, 14], [-120, 30], 'l'),
    c('send', '圖傳', [284, 380, 242], [-200, -40], 'l'),
  ]));
  return out.join('\n');
}

export default {
  id: 'drone',
  name: '空拍機',
  slots: {
    sense: '慣性感測器（IMU）量傾斜，GPS 定位，氣壓計量高度。',
    decide: '飛控板依遙控指令和定位資料，決定往哪飛、飛多高。',
    act: '電子調速器控制四顆馬達的轉速。',
    record: '飛行紀錄存在飛控，影片存在記憶卡。',
    send: '遙控指令往上送，即時影像與電量往回傳。',
  },
  loop: {
    sentence: 'IMU 量到機身傾斜，飛控板立刻調整馬達轉速，機身再回到水平。',
    edges: [['sense', 'decide'], ['decide', 'act'], ['act', 'sense']],
  },
  edges: [
    ['sense', 'decide'], ['decide', 'act'], ['act', 'sense'],
    ['sense', 'record'], ['send', 'decide'], ['sense', 'send'],
  ],
  traps: [
    '遙控訊號斷了，要原地降落還是自動返航？',
    '在室內或橋下收不到 GPS，怎麼定位？',
    '風太大，馬達出力不夠，多大的風就不該飛？',
    '天氣冷，電池電壓掉得太快，起飛前要先做什麼？',
    '指南針被金屬干擾，飛控怎麼知道方向錯了？',
  ],
  scene,
};
