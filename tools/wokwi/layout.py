"""Wokwi wiring diagrams for the Uno alarm handout (handout/alarm-uno.html, steps 1–4).
Regenerate:
  python3 tools/wokwi/layout.py /tmp/wk                       # writes step1..4.json + .bounds.json
  for n in 1 2 3 4; do cp /tmp/wk/step4.bounds.json /tmp/wk/step$n.bounds.json; done   # same framing every step
  node tools/wokwi/shoot.mjs /tmp/wk/stepN.json /tmp/wk/stepN.png 24 2   # renders on wokwi.com (needs network)
  cwebp -q 82 -resize 1400 0 /tmp/wk/stepN.png -o assets/handout/wokwi/uno-stepN.webp
  cp /tmp/wk/stepN.json handout/code/wokwi/uno-stepN/diagram.json
gen.py turns absolute waypoints into Wokwi's v/h wire moves (Wokwi drops a final segment that is exactly
lined up with the target pin, so gen.py nudges it by half a pixel).

Uno alarm wiring, all parts. Pins: HC-SR04 TRIG D4 / ECHO D3, LED R D11 / G D10 / B D9 (common cathode),
buzzer + D12 / - GND, light module AO A0, knob A1. Every step's diagram is a subset of this one."""
import json, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from gen import Board, build, UNO, pin_abs

bb = Board("bb1", 69.6, 150)
H, R = bb.hole, bb.rail
UX, UY = 0, 420
def U(pin): x, y = UNO[pin]; return (UX + x, UY + y)

lx, ly = H(6, "d")
PARTS = {
  "uno":   {"type": "wokwi-arduino-uno", "id": "uno", "left": UX, "top": UY},
  "ldr":   {"type": "wokwi-photoresistor-sensor", "id": "ldr", "left": -130, "top": 20},
  "sonar": {"type": "wokwi-hc-sr04", "id": "sonar", "left": 136.2, "top": 20},
  "pot":   {"type": "wokwi-potentiometer", "id": "pot", "left": 330, "top": 30},
  "bz":    {"type": "wokwi-buzzer", "id": "bz", "left": -20, "top": 210, "attrs": {"volume": "0.1"}},
  "rgb":   {"type": "wokwi-rgb-led", "id": "rgb", "left": round(lx - 8.5, 2), "top": round(ly - 44, 2), "attrs": {"common": "cathode"}},
}
for rid, col in (("r1", 6), ("r2", 8), ("r3", 9)):
    x, y = H(col, "e")
    PARTS[rid] = {"type": "wokwi-resistor", "id": rid, "left": round(x - 29.55, 2), "top": round(y + 23.9, 2), "rotate": 90, "attrs": {"value": "220"}}
def P(pid, pin): return pin_abs(PARTS[pid], pin)

# wires grouped by the part they belong to
W = {}
x5, _ = U("5V"); xg, _ = U("GND.2")
W["power"] = [
  ["uno:5V", "bb1:tp.1", "red", [(x5, 655), (-55, 655), (-55, R("tp", 1)[1])]],
  ["uno:GND.2", "bb1:tn.1", "black", [(xg, 645), (-45, 645), (-45, R("tn", 1)[1])]],
]
lv, lg, la = P("ldr", "VCC"), P("ldr", "GND"), P("ldr", "AO")
W["ldr"] = [
  ["ldr:VCC", "bb1:tp.3", "red", [(R("tp", 3)[0], lv[1])]],
  ["ldr:GND", "bb1:tn.2", "black", [(R("tn", 2)[0], lg[1])]],
  ["ldr:AO", "uno:A0", "orange", [(la[0] + 10, la[1]), (la[0] + 10, 100), (-65, 100), (-65, 670), (U("A0")[0], 670)]],
]
sv, sg = P("sonar", "VCC"), P("sonar", "GND")
W["sonar"] = [
  ["sonar:VCC", "bb1:tp.10", "red", [(sv[0], 148), (R("tp", 10)[0], 148)]],
  ["sonar:GND", "bb1:tn.14", "black", [(sg[0], 150), (R("tn", 14)[0], 150)]],
  ["sonar:TRIG", "uno:4", "yellow", []],
  ["sonar:ECHO", "uno:3", "cyan", []],
]
W["led"] = [["rgb:R", "bb1:6t.d", "$bb"], ["rgb:COM", "bb1:7t.e", "$bb"], ["rgb:G", "bb1:8t.d", "$bb"], ["rgb:B", "bb1:9t.d", "$bb"],
            ["bb1:7t.a", "bb1:tn.6", "black", [(H(7, "a")[0], 188), (R("tn", 6)[0], 188)]]]
for rid, col in (("r1", 6), ("r2", 8), ("r3", 9)):
    W["led"] += [[f"{rid}:1", f"bb1:{col}t.e", "$bb"], [f"{rid}:2", f"bb1:{col}b.i", "$bb"]]
for col, pin, color, yy in ((6, "11", "red", 380), (8, "10", "green", 388), (9, "9", "blue", 396)):
    W["led"].append([f"bb1:{col}b.j", f"uno:{pin}", color, [(H(col, "j")[0], yy), (U(pin)[0], yy)]])
b1, b2 = P("bz", "1"), P("bz", "2")
W["bz"] = [
  ["bz:2", "uno:12", "magenta", [(b2[0], 405), (U("12")[0], 405)]],
  ["bz:1", "uno:GND.1", "black", [(b1[0], 415), (U("GND.1")[0], 415)]],
]
pg, ps, pv = P("pot", "GND"), P("pot", "SIG"), P("pot", "VCC")
W["pot"] = [
  ["pot:GND", "bb1:tn.24", "black", [(pg[0], 140), (R("tn", 24)[0], 140)]],
  ["pot:VCC", "bb1:tp.25", "red", [(pv[0], 140), (R("tp", 25)[0], 140)]],
  ["pot:SIG", "uno:A1", "violet", [(ps[0], 195), (430, 195), (430, 680), (U("A1")[0], 680)]],
]

STEPS = {   # which parts each step's diagram shows
  1: ["uno", "ldr"],
  2: ["uno", "ldr", "sonar"],
  3: ["uno", "ldr", "sonar", "rgb", "r1", "r2", "r3", "bz"],
  4: ["uno", "ldr", "sonar", "rgb", "r1", "r2", "r3", "bz", "pot"],
}
GROUP = {"ldr": "ldr", "sonar": "sonar", "rgb": "led", "bz": "bz", "pot": "pot"}

def step(n):
    ids = STEPS[n]
    parts = [PARTS[i] for i in ids]
    wires = list(W["power"])
    for i in ids:
        if i in GROUP: wires += W[GROUP[i]]
    return build(parts, {"bb1": bb}, wires)

if __name__ == "__main__":
    out = sys.argv[1]
    for n in STEPS:
        d = step(n)
        json.dump(d.pop("_bounds"), open(f"{out}/step{n}.bounds.json", "w"))
        json.dump(d, open(f"{out}/step{n}.json", "w"), indent=2, ensure_ascii=False)
    print("ok")
