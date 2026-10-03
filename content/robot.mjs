// Example: delivery robot, drawn as an exploded view on a restaurant floor.

const LOOP_PARTS = new Set(['encoder', 'board-main', 'board-driver', 'motor']);

const ring = (n, f) => {
  const a = [];
  for (let i = 0; i < n; i++) {
    const t = (i / n) * Math.PI * 2;
    a.push(f(Math.cos(t), Math.sin(t)));
  }
  return a;
};

function scene(iso) {
  const { P, poly, line } = iso;
  const add = (slot, part, box, decor) => iso.add(slot, part, box, decor, LOOP_PARTS.has(part));

  // the robot sits RX along the floor; everything of the robot is written in its own coordinates
  const RS = 1.15;
  const rx = (x) => 432 + RS * (x - 282);
  const ry = (y) => 220 + RS * (y - 220);
  const rz = (z) => RS * z;
  const Q = (x, y, z) => P(rx(x), ry(y), rz(z));
  const radd = (slot, part, b, decor) =>
    add(slot, part, [rx(b[0]), rx(b[1]), ry(b[2]), ry(b[3]), rz(b[4]), rz(b[5])], decor);

  // flat shapes in the robot's coordinates
  const discY = (cls, xc, y, zc, r) => poly(cls, ring(30, (c, s) => Q(xc + r * c, y, zc + r * s)));
  const discZ = (cls, xc, yc, z, r) => poly(cls, ring(30, (c, s) => Q(xc + r * c, yc + r * s, z)));
  const rectY = (cls, x0, x1, y, z0, z1) => poly(cls, [Q(x0, y, z0), Q(x1, y, z0), Q(x1, y, z1), Q(x0, y, z1)]);
  const rectX = (cls, x, y0, y1, z0, z1) => poly(cls, [Q(x, y0, z0), Q(x, y1, z0), Q(x, y1, z1), Q(x, y0, z1)]);
  // the same for objects given in floor coordinates
  const fX = (cls, x, y0, y1, z0, z1) => poly(cls, [P(x, y0, z0), P(x, y1, z0), P(x, y1, z1), P(x, y0, z1)]);

  // ---------- geometry ----------
  const FW = 990, FY0 = 60, FY1 = 380;
  const HX = 348, HZ = 25, WR = 25;       // wheel hub x, hub height, radius
  const NEAR_W = 338, FAR_W = 112;        // wheel planes (y)
  const out = [];

  // a tire: dark tread ring, paper face, small hub cap
  const tire = (y) =>
    discY('wheel', HX, y, HZ, WR) + discY('plate', HX, y + 0.3, HZ, WR - 6) + discY('plate', HX, y + 0.6, HZ, 6);

  // ---------- floor with faint tiles ----------
  let tiles = '';
  const T = 100;
  for (let x = 0; x < FW; x += T)
    for (let y = FY0; y < FY1; y += 80)
      tiles += iso.groundRect('ground', [x, Math.min(x + T, FW), y, y + 80]);
  out.push(iso.group('base', 'ground', tiles));

  // far wheel (behind the base, drawn before everything that stands on the floor)
  out.push(iso.group('act', 'wheel', tire(FAR_W)));

  // planned route (decide) and wireless links (send), flat on the floor
  const TX = 850;
  out.push(iso.group('decide', 'route',
    iso.netPath([[rx(428) + 4, 220], [690, 220], [690, 278], [TX - 4, 278]])));
  out.push(iso.group('send', 'network',
    iso.netPath([[130, 100], [130, 238], [94, 238]]) +
    iso.netPath([[94, 226], [118, 226], [118, 100]]) +
    iso.netPath([[144, 70], [290, 70], [290, 185], [425, 185]]) +
    iso.netPath([[425, 197], [278, 197], [278, 82], [144, 82]])));

  // ---------- table (4 legs) and chairs ----------
  const leg = (part, x, y, h) => add('base', part, [x, x + 8, y, y + 8, 0, h]);
  for (const [x, y] of [[TX + 6, 161], [TX + 116, 161], [TX + 6, 271], [TX + 116, 271]]) leg('table', x, y, 165);
  add('base', 'table', [TX, TX + 130, 155, 285, 165, 173]);
  const chair = (x0, y0, backSide) => {
    for (const [dx, dy] of [[0, 0], [44, 0], [0, 44], [44, 44]]) add('base', 'chair', [x0 + dx, x0 + dx + 6, y0 + dy, y0 + dy + 6, 0, 94]);
    add('base', 'chair', [x0, x0 + 50, y0, y0 + 50, 94, 102]);
    if (backSide === 'x') add('base', 'chair', [x0, x0 + 6, y0, y0 + 50, 102, 165]);
    else add('base', 'chair', [x0, x0 + 50, y0, y0 + 6, 102, 165]);
  };
  chair(TX - 88, 195, 'x');
  chair(TX + 40, 90, 'y');

  // ---------- counter and tablet ----------
  add('base', 'counter', [10, 86, 160, 300, 0, 120]);
  add('base', 'counter', [4, 92, 154, 306, 120, 128]);
  add('send', 'tablet', [42, 72, 214, 246, 128, 138]);
  const TAB = [50, 60, 205, 255, 138, 180];
  add('send', 'tablet', TAB, () => fX('screen', TAB[1] + 0.3, 211, 249, 145, 174));

  // ---------- access point on a pillar ----------
  add('base', 'pillar', [112, 128, 66, 82, 0, 185]);
  add('send', 'ap', [98, 142, 52, 96, 185, 203]);
  add('send', 'ap', [104, 109, 57, 62, 203, 241]);
  add('send', 'ap', [131, 136, 86, 91, 203, 241]);

  // ---------- robot: drive base (top cover removed) ----------
  radd('base', 'chassis', [282, 418, 152, 288, 10, 16], () => line('detail', Q(288, 288.3, 13), Q(412, 288.3, 13)));
  // front caster, tucked under the front edge
  radd('base', 'caster', [410, 428, 214, 226, 6, 10], () => discY('wheel', 419, 226.3, 6, 6));
  // boards laid flat inside
  radd('decide', 'board-main', [326, 370, 198, 242, 16, 20], () => {
    let o = '';
    for (const a of [331, 341, 351]) o += poly('plate', [Q(a, 202, 20), Q(a + 6, 202, 20), Q(a + 6, 214, 20), Q(a, 214, 20)]);
    return o;
  });
  radd('record', 'chip', [336, 360, 222, 238, 20, 28], () => line('detail', Q(348, 238.3, 24), Q(358, 238.3, 24)));
  radd('act', 'board-driver', [288, 318, 172, 268, 16, 20]);
  // wheel motors with encoders on their outer ends
  radd('act', 'motor', [326, 370, 250, 282, 16, 34]);
  radd('sense', 'encoder', [342, 354, 282, 292, 14, 36]);
  radd('act', 'motor', [326, 370, 158, 190, 16, 34]);
  radd('sense', 'encoder', [342, 354, 148, 158, 14, 36]);
  // lidar puck, low and wide, at the front
  const PK = [378, 412, 196, 244, 16, 32];
  radd('sense', 'lidar', PK, () =>
    rectY('screen', 384, 406, PK[3] + 0.3, 22, 27) + rectX('screen', PK[1] + 0.3, 204, 236, 22, 27));

  // ---------- upper body: spine along the back, 3 trays, head ----------
  radd('base', 'body', [292, 316, 200, 240, 64, 110]);
  radd('base', 'body', [292, 410, 160, 280, 110, 118]);
  radd('base', 'body', [292, 316, 200, 240, 118, 170]);
  radd('base', 'body', [292, 410, 160, 280, 170, 178]);
  radd('base', 'body', [292, 316, 200, 240, 178, 230]);
  radd('base', 'body', [292, 410, 160, 280, 230, 238]);
  radd('base', 'body', [292, 316, 200, 240, 238, 290]);
  const HEAD = [288, 332, 188, 252, 290, 332];
  radd('base', 'head', HEAD, () => rectX('screen', HEAD[1] + 0.3, 196, 244, 298, 324));
  const CAM = [316, 324, 212, 228, 252, 270];
  radd('sense', 'camera', CAM, () => rectX('screen', CAM[1] + 0.3, 215, 225, 256, 266));
  // bowl on the top tray
  radd('base', 'bowl', [350, 394, 198, 242, 238, 252], () => discZ('plate', 372, 220, 252.3, 17) + discZ('plate', 372, 220, 252.6, 10));

  // ---------- exploded-view alignment lines ----------
  let align = '';
  for (const [x, y] of [[292, 160], [410, 160], [292, 280], [410, 280]]) align += line('cone', Q(x, y, 110), Q(x, y, 16));
  const axle = (y0, y1) => line('cone', Q(HX, y0, HZ), Q(HX, y1, HZ));

  out.push(iso.items());
  // near wheel (in front of the base)
  out.push(iso.group('act', 'wheel', tire(NEAR_W)));
  out.push(iso.group('base', 'align', align + axle(292, NEAR_W) + axle(148, FAR_W)));

  const A = (x, y, z) => [rx(x), ry(y), rz(z)];
  out.push(iso.callouts([
    { slot: 'sense', part: 'lidar', text: '光達', a: A(412, 220, 32), d: [-10, 150], side: 'l' },
    { slot: 'sense', part: 'camera', text: '攝影機', a: A(324, 220, 270), d: [170, -60], side: 'r' },
    { slot: 'sense', part: 'encoder', text: '編碼器', a: A(348, 287, 36), d: [-100, 150], side: 'l', loop: true },
    { slot: 'decide', part: 'board-main', text: '主控板', a: A(370, 220, 20), d: [190, -150], side: 'r', loop: true },
    { slot: 'act', part: 'board-driver', text: '馬達驅動板', a: A(288, 220, 20), d: [-165, 22], side: 'l', loop: true },
    { slot: 'act', part: 'motor', text: '輪子馬達', a: A(348, 266, 34), d: [-190, 60], side: 'l', loop: true },
    { slot: 'record', part: 'chip', text: '儲存裝置', a: A(348, 230, 28), d: [-125, 8], side: 'l' },
    { slot: 'send', part: 'ap', text: '無線基地台', a: [120, 74, 241], d: [-140, -80], side: 'l' },
    { slot: 'send', part: 'tablet', text: '櫃台平板', a: [60, 230, 180], d: [-150, -50], side: 'l' },
  ]));
  return out.join('\n');
}

export default {
  id: 'robot',
  name: '送餐機器人',
  slots: {
    sense: '光達與攝影機看前方，輪子編碼器算出走了多遠。',
    decide: '主控板規劃路線，遇到障礙決定停下或繞過。',
    act: '馬達驅動板控制左右輪的轉速。',
    record: '存下店內地圖和每一趟的行駛紀錄。',
    send: '透過 Wi-Fi 接收送餐指令，回報位置與電量。',
  },
  loop: {
    sentence: '編碼器量到輪子轉了多少，主控板再修正馬達轉速。',
    edges: [['sense', 'decide'], ['decide', 'act'], ['act', 'sense']],
  },
  edges: [
    ['sense', 'decide'], ['decide', 'act'], ['act', 'sense'],
    ['record', 'decide'], ['sense', 'record'], ['send', 'decide'], ['decide', 'send'],
  ],
  traps: [
    '怕走到一半沒電，剩多少電就該回去充電？',
    '有人突然走到前面，要急停還是繞過？',
    'Wi-Fi 斷線，機器人要停下還是繼續送？',
    '輪子打滑，位置算錯了，機器人怎麼發現？',
    '地板反光或桌腳太細，感測器沒看到，要加裝什麼？',
  ],
  scene,
};
