// Exports the 3D geometry of every scene (boxes, flat polygons, lines, in world units) for the Blender pipeline.
// Run: node tools/export3d.mjs <outDir>   -> <outDir>/robot.json, drone.json, parking.json
import fs from 'node:fs';
import path from 'node:path';
import { recordScene } from './lib/iso.mjs';
import robot from '../content/robot.mjs';
import drone from '../content/drone.mjs';
import parking from '../content/parking.mjs';

const outArg = process.argv[2];
if (!outArg) {
  console.error('usage: node tools/export3d.mjs <outDir>');
  process.exit(1);
}
const outDir = path.resolve(outArg);
fs.mkdirSync(outDir, { recursive: true });

// 4 decimals are plenty (1e-4 of a drawing unit) and keep the files readable
const round = (_, v) => (typeof v === 'number' ? Math.round(v * 1e4) / 1e4 : v);
const json = (v) => JSON.stringify(v, round);

// one primitive per line
function serialize({ boxes, polys, lines, ...head }) {
  const fields = Object.entries(head).map(([k, v]) => `  ${json(k)}: ${json(v)}`);
  const lists = Object.entries({ boxes, polys, lines }).map(
    ([k, a]) => `  ${json(k)}: [\n${a.map((o) => '    ' + json(o)).join(',\n')}\n  ]`
  );
  return '{\n' + [...fields, ...lists].join(',\n') + '\n}\n';
}

for (const ex of [robot, drone, parking]) {
  const rec = recordScene(ex.scene);
  const file = path.join(outDir, ex.id + '.json');
  fs.writeFileSync(file, serialize({ id: ex.id, ...rec }));
  console.log(ex.id, `viewBox ${rec.w}x${rec.h}`, `boxes ${rec.boxes.length} polys ${rec.polys.length} lines ${rec.lines.length}`, '->', file);
}
