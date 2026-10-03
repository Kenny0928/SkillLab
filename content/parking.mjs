// Example: parking-lot entrance / exit.

const LANE = { x0: 0, x1: 880, y0: 0, y1: 300 };
const LOOP_PARTS = new Set(['server', 'database', 'controller']);

function scene(iso) {
  const { P, poly, line, K, S } = iso;
  // box = [x0,x1,y0,y1,z0,z1]
  const add = (slot, part, box, decor) => iso.add(slot, part, box, decor, LOOP_PARTS.has(part));

  // car (faces +x, toward the barrier)
  const CAR = [180, 560, 65, 235, 25, 80];
  add('base', 'car', CAR, () => {
    const [, x1, , y1] = CAR;
    const wheel = (xc, zc, r) => {
      const a = [];
      for (let i = 0; i < 28; i++) {
        const t = (i / 28) * Math.PI * 2;
        a.push(P(xc + r * Math.cos(t), y1 + 0.3, zc + r * Math.sin(t)));
      }
      return poly('wheel', a);
    };
    // plate on the +x (front) face
    const px = x1 + 0.3, py0 = 122, py1 = 178, pz0 = 38, pz1 = 60;
    const plate = poly('plate', [P(px, py0, pz0), P(px, py1, pz0), P(px, py1, pz1), P(px, py0, pz1)]);
    const o = P(px, py1, pz1);
    const m = `matrix(${(K * S).toFixed(4)} ${(-0.5 * S).toFixed(4)} 0 ${S} ${o[0].toFixed(1)} ${o[1].toFixed(1)})`;
    const W = py1 - py0;
    const text = `<text class="t-plate" transform="${m}" x="${W / 2}" y="15" text-anchor="middle" font-size="9.6">ABC-1234</text>`;
    return wheel(258, 27, 27) + wheel(480, 27, 27) + plate + text;
  });
  add('base', 'car', [300, 480, 90, 210, 80, 122]);

  // sense: camera on the back side, aimed at the plate
  const CAMH = [570, 624, -100, -62, 166, 194];
  add('sense', 'camera', [590, 604, -90, -76, 0, 166]);
  add('sense', 'camera', CAMH, () => {
    const y = CAMH[3] + 0.3;
    const lens = poly('screen', [P(588, y, 174), P(606, y, 174), P(606, y, 187), P(588, y, 187)]);
    const l = P(597, y, 180.5);
    const t1 = P(560.5, 122, 60);
    const t2 = P(560.5, 178, 38);
    return lens + line('cone', l, t1) + line('cone', l, t2);
  });

  // act: display (post + panel), barrier (cabinet + arm)
  const DISP = [640, 730, -70, -56, 105, 180];
  add('act', 'display', [680, 690, -66, -60, 0, 105]);
  add('act', 'display', DISP, () => {
    const y = DISP[3] + 0.3;
    const x0 = 648, x1 = 722, z0 = 113, z1 = 172;
    const scr = poly('screen', [P(x0, y, z0), P(x1, y, z0), P(x1, y, z1), P(x0, y, z1)]);
    const o = P(x0, y, z1);
    const m = `matrix(${(K * S).toFixed(4)} ${(0.5 * S).toFixed(4)} 0 ${S} ${o[0].toFixed(1)} ${o[1].toFixed(1)})`;
    const text = `<text class="t-screen" transform="${m}" x="${(x1 - x0) / 2}" y="${(z1 - z0) / 2 + 4}" text-anchor="middle" font-size="12">ABC-1234</text>`;
    return scr + text;
  });
  add('act', 'barrier', [760, 820, -80, -10, 0, 120]);
  add('act', 'barrier', [780, 798, -10, 300, 95, 107]);

  // decide: field controller
  add('decide', 'controller', [840, 900, -90, -30, 0, 110], () => {
    const y = -30 + 0.3;
    return line('detail', P(850, y, 78), P(890, y, 78)) + line('detail', P(850, y, 62), P(890, y, 62));
  });

  // record: database (base + stacked units)
  add('record', 'database', [830, 890, -190, -140, 0, 10]);
  add('record', 'database', [836, 884, -184, -146, 10, 28]);
  add('record', 'database', [836, 884, -184, -146, 28, 46]);
  add('record', 'database', [836, 884, -184, -146, 46, 64]);

  // send: server (remote, upper right, own slab) and kiosk (lower right, own slab)
  add('send', 'server', [880, 1000, -360, -260, 0, 8]);
  add('send', 'server', [910, 970, -340, -280, 8, 143], () => {
    const out = [];
    for (const z of [40, 70, 100, 125]) {
      out.push(line('detail', P(918, -279.7, z), P(962, -279.7, z)));
      out.push(line('detail', P(970.3, -332, z), P(970.3, -288, z)));
    }
    return out.join('');
  });
  add('send', 'kiosk', [980, 1080, 320, 420, 0, 8]);
  const KIOSK = [1010, 1070, 350, 410, 8, 160];
  add('send', 'kiosk', KIOSK, () => {
    const y = KIOSK[3] + 0.3;
    const scr = poly('screen', [P(1018, y, 96), P(1062, y, 96), P(1062, y, 140), P(1018, y, 140)]);
    const slot = poly('screen', [P(1028, y, 60), P(1052, y, 60), P(1052, y, 66), P(1028, y, 66)]);
    return scr + slot;
  });

  const out = [];
  // ground
  out.push(iso.group('base', 'ground',
    iso.groundRect('ground', [LANE.x0, LANE.x1, LANE.y0, LANE.y1]) +
    iso.groundLine('lane-edge', [LANE.x0, 14], [LANE.x1, 14]) +
    iso.groundLine('lane-edge', [LANE.x0, 286], [LANE.x1, 286]) +
    iso.groundRect('stop', [700, 712, 0, 300])));
  // loop detector (flat, on the ground, partly under the car)
  out.push(iso.group('sense', 'loop', iso.groundRect('loop', [490, 660, 60, 240])));
  // network paths: controller <-> server both ways (lit with the step-6 loop), server -> kiosk
  out.push(iso.group('send', 'network',
    iso.netPath([[904, -60], [940, -60], [940, -258]]) +
    iso.netPath([[952, -258], [952, -48], [904, -48]]), true));
  out.push(iso.group('send', 'network',
    iso.netPath([[1000, -310], [1030, -310], [1030, 312]])));
  out.push(iso.items());

  // callouts: anchor in world coords; d = label point relative to the anchor, in drawing px
  out.push(iso.callouts([
    { slot: 'sense', part: 'loop', text: '地感線圈', a: [650, 235, 0], d: [-60, 130], side: 'l' },
    { slot: 'sense', part: 'camera', text: '車牌辨識攝影機', a: [597, -81, 194], d: [-110, -90], side: 'l' },
    { slot: 'decide', part: 'controller', text: '現場控制器', a: [900, -60, 45], d: [120, 110], side: 'r', loop: true },
    { slot: 'act', part: 'display', text: '顯示幕', a: [685, -63, 180], d: [-90, -120], side: 'l' },
    { slot: 'act', part: 'barrier', text: '柵欄機', a: [789, 296, 107], d: [-60, 150], side: 'l' },
    { slot: 'record', part: 'database', text: '資料庫', a: [860, -165, 64], d: [40, -230], side: 'r', loop: true },
    { slot: 'send', part: 'server', text: '伺服器', a: [940, -310, 143], d: [60, -110], side: 'r', loop: true },
    { slot: 'send', part: 'kiosk', text: '繳費機', a: [1020, 410, 120], d: [-90, 10], side: 'l' },
  ]));
  return out.join('\n');
}

export default {
  id: 'parking',
  name: '停車場',
  slots: {
    sense: '地感線圈偵測到車，攝影機拍下車牌。',
    decide: '辨識車牌，比對是不是月租車。',
    act: '柵欄機抬起柵欄，顯示幕秀出車牌。',
    record: '存下車牌、進場時間與照片。',
    send: '現場控制器把紀錄送到伺服器，繳費機再用車牌查回來。',
  },
  loop: {
    sentence: '月租名單由伺服器傳到現場，判斷才知道這台車要不要收費。',
    edges: [['send', 'record'], ['record', 'decide']],
  },
  edges: [
    ['sense', 'decide'], ['decide', 'act'], ['record', 'decide'],
    ['decide', 'record'], ['record', 'send'], ['send', 'record'],
  ],
  traps: [
    '網路斷了，柵欄要不要開？',
    '有人跟著前車出去，柵欄要多快放下？',
    '晚上或下雨，車牌拍不清楚，要放行還是人工確認？',
    '車牌認錯一個字，出場查不到進場紀錄，要收多少錢？',
    '柵欄放下前，怎麼確定車子已經離開？',
  ],
  scene,
};
