// Packs handout/code/starter/ into handout/skilllab.zip (one top folder, skilllab/), the
// 課程資料夾 that the 環境安裝 handout links to. Run after editing any starter file:
//   node tools/starter-zip.mjs
// uv.lock is generated, not hand-edited: after changing pyproject.toml run `uv lock` in
// handout/code/starter first.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = path.join(root, 'handout', 'code', 'starter');
const out = path.join(root, 'handout', 'skilllab.zip');
const skip = new Set(['.venv', '__pycache__', '.DS_Store', 'config.json']);

const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'skilllab-'));
const dest = path.join(stage, 'skilllab');
fs.cpSync(src, dest, { recursive: true, filter: f => !skip.has(path.basename(f)) });
if (!fs.existsSync(path.join(dest, 'uv.lock'))) throw new Error('uv.lock missing: run `uv lock` in handout/code/starter');

fs.rmSync(out, { force: true });
execFileSync('zip', ['-r', '-X', '-q', out, 'skilllab'], { cwd: stage });
fs.rmSync(stage, { recursive: true, force: true });
console.log(execFileSync('unzip', ['-l', out]).toString());
