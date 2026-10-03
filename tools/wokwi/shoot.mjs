// node tools/wokwi/shoot.mjs <diagram.json> <out.png> [pad=16] [scale=2] — see layout.py for the full pipeline
// Loads the diagram into a fresh Wokwi project, hides the UI and screenshots just the drawing.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const [diagPath, out, padArg, scaleArg] = process.argv.slice(2);
const pad = Number(padArg || 16), scale = Number(scaleArg || 2);
const diagram = fs.readFileSync(diagPath, 'utf8');
const port = 9400 + Math.floor(Math.random()*90);
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${process.env.TMPDIR}/wc-${port}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let list; for (let i=0;i<50&&!list;i++){ try{ list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); }catch{ await sleep(200);} }
const ws = new WebSocket(list.find(t=>t.type==='page').webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
let id=0; const pend=new Map(); ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}};
const send=(method,params={})=>new Promise(r=>{const i=++id;pend.set(i,r);ws.send(JSON.stringify({id:i,method,params}));});
const ev=async x=>{const r=await send('Runtime.evaluate',{expression:x,returnByValue:true,awaitPromise:true}); return r.result?.exceptionDetails ? 'ERR '+JSON.stringify(r.result.exceptionDetails.exception?.description) : r.result?.result?.value;};
await send('Emulation.setDeviceMetricsOverride',{width:2600,height:2200,deviceScaleFactor:scale,mobile:false});
await send('Page.enable'); await send('Page.navigate',{url:'https://wokwi.com/projects/new/arduino-uno'}); await sleep(9000);
await ev(`(()=>{const t=[...document.querySelectorAll('[role=tab], button, div')].find(b=>b.textContent.trim()==='diagram.json'); t&&t.click();})()`); await sleep(2000);
console.log(await ev(`(()=>{const m=monaco.editor.getModels().find(m=>m.uri.path.endsWith('diagram.json')); m.setValue(${JSON.stringify(diagram)}); return 'set';})()`));
await sleep(3500);
// find the diagram layer (parent of the parts) and measure parts + wires
const box = JSON.parse(await ev(`(()=>{
  const parts=[...document.querySelectorAll('[class*=diagramItem]')];
  const wires=[...document.querySelectorAll('[class*=wire] path, [class*=Wire] path, g[class*=wire], g[class*=Wire]')];
  window.__dbg = {parts: parts.length, wires: wires.length, wireCls: [...new Set(wires.map(w=>w.getAttribute('class')))].slice(0,5)};
  const all=[...parts, ...wires].filter(e=>{const r=e.getBoundingClientRect(); return r.width>0||r.height>0;});
  let x1=1e9,y1=1e9,x2=-1e9,y2=-1e9;
  for(const e of all){const r=e.getBoundingClientRect(); x1=Math.min(x1,r.left);y1=Math.min(y1,r.top);x2=Math.max(x2,r.right);y2=Math.max(y2,r.bottom);}
  return JSON.stringify({x1,y1,x2,y2,dbg:window.__dbg});
})()`));
console.log(JSON.stringify(box));
let clip = { x: box.x1 - pad, y: box.y1 - pad, width: box.x2 - box.x1 + 2*pad, height: box.y2 - box.y1 + 2*pad, scale: 1 };
const bpath = diagPath.replace(/\.json$/, '.bounds.json');
if (fs.existsSync(bpath)) {
  const b = JSON.parse(fs.readFileSync(bpath, 'utf8'));
  const u = JSON.parse(await ev(`JSON.stringify(document.querySelector('wokwi-arduino-uno').getBoundingClientRect())`));
  const z = u.width / 274.3, sx = x => u.left + z * (x - b.unoLeft), sy = y => u.top + z * (y - b.unoTop);
  clip = { x: sx(b.x1) - pad, y: sy(b.y1) - pad, width: z * (b.x2 - b.x1) + 2 * pad, height: z * (b.y2 - b.y1) + 2 * pad, scale: 1 };
}
if (process.env.DUMP) console.log(await ev(`JSON.stringify([...document.querySelectorAll('path, polyline')].filter(p=>{const s=getComputedStyle(p).stroke; return /[0-9]/.test(p.getAttribute('d')||'') && !p.closest('[class*=diagramItem]') && !p.closest('wokwi-arduino-uno, wokwi-hc-sr04');}).map(p=>({d:(p.getAttribute('d')||p.getAttribute('points')||'').slice(0,160), cls:p.getAttribute('class'), parent:p.parentElement.getAttribute('class')})).slice(0,12))`));
const shot = await send('Page.captureScreenshot',{format:'png', captureBeyondViewport:true, clip});
fs.writeFileSync(out, Buffer.from(shot.result.data,'base64'));
ws.close(); chrome.kill();
