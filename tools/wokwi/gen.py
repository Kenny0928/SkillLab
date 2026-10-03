"""Builds Wokwi diagram.json files for the Uno alarm steps from absolute coordinates.
Wires are given as absolute waypoints; they are converted to Wokwi's relative v/h moves."""
import json, sys

UNO = {"A5.2":(87,9),"A4.2":(97,9),"AREF":(106,9),"GND.1":(115.5,9),"13":(125,9),"12":(134.5,9),"11":(144,9),"10":(153.5,9),"9":(163,9),"8":(173,9),"7":(189,9),"6":(198.5,9),"5":(208,9),"4":(217.5,9),"3":(227,9),"2":(236.5,9),"1":(246,9),"0":(255.5,9),
       "IOREF":(131,191.5),"RESET":(140.5,191.5),"3.3V":(150,191.5),"5V":(160,191.5),"GND.2":(169.5,191.5),"GND.3":(179,191.5),"VIN":(188.5,191.5),"A0":(208,191.5),"A1":(217.5,191.5)}
PINS = {
 "wokwi-arduino-uno": UNO,
 "wokwi-hc-sr04": {"VCC":(71.3,94.5),"TRIG":(81.3,94.5),"ECHO":(91.3,94.5),"GND":(101.3,94.5)},
 "wokwi-photoresistor-sensor": {"VCC":(172,16),"GND":(172,26),"DO":(172,35.8),"AO":(172,45.5)},
 "wokwi-potentiometer": {"GND":(29,68.5),"SIG":(39,68.5),"VCC":(49,68.5)},
 "wokwi-buzzer": {"1":(27,84),"2":(37,84)},
 "wokwi-rgb-led": {"R":(8.5,44),"COM":(18,54),"G":(26.4,44),"B":(35.7,44)},
 "wokwi-resistor": {"1":(0,5.65),"2":(58.8,5.65)},
}
SIZE = {"wokwi-resistor":(59.1,11.3), "wokwi-arduino-uno":(274.3,201.6), "wokwi-hc-sr04":(170.1,94.5), "wokwi-photoresistor-sensor":(173.7,61.5), "wokwi-potentiometer":(75.6,75.6), "wokwi-buzzer":(75,83.6), "wokwi-rgb-led":(42.1,72.6)}
ROWS = dict(a=50.79,b=60.39,c=69.99,d=79.59,e=89.19,f=118.79,g=128.39,h=137.99,i=147.59,j=157.19)
RAIL = dict(tp=12.69,tn=22.29,bp=186.49,bn=196.09)

class Board:
    def __init__(s, id, left, top): s.id, s.left, s.top = id, left, top
    def hole(s, col, row): return (s.left + 26.39 + 9.6*(col-1), s.top + ROWS[row])
    def rail(s, name, k): return (s.left + 34.89 + 57.6*((k-1)//5) + 9.6*((k-1)%5), s.top + RAIL[name])

def pin_abs(part, pin):
    x, y = PINS[part["type"]][pin]
    if part.get("rotate") == 90:
        w, h = SIZE[part["type"]]; cx, cy = w/2, h/2
        x, y = cx - (y - cy), cy + (x - cx)
    return (part["left"] + x, part["top"] + y)

def build(parts, boards, wires):
    byid = {p["id"]: p for p in parts}
    def where(ref):
        pid, pin = ref.split(":", 1)
        if pid in byid: return pin_abs(byid[pid], pin)
        b = boards[pid]
        if "." in pin and pin.split(".")[0] in RAIL: r, k = pin.split("."); return b.rail(r, int(k))
        col, row = pin[:-3], pin[-1]  # e.g. 22t.e / 22b.i
        return b.hole(int(col), row)
    conns = []
    xs, ys = [], []
    for p in parts:
        w_, h_ = SIZE[p["type"]]
        if p.get("rotate") == 90: cx, cy = p["left"] + w_/2, p["top"] + h_/2; xs += [cx - h_/2, cx + h_/2]; ys += [cy - w_/2, cy + w_/2]
        else: xs += [p["left"], p["left"] + w_]; ys += [p["top"], p["top"] + h_]
    for b in boards.values(): xs += [b.left, b.left + 328.8]; ys += [b.top, b.top + 207.9]
    for w in wires:
        src, dst, color, *rest = w
        pts = rest[0] if rest else []
        tail = rest[1] if len(rest) > 1 else []   # moves applied from the target pin
        if color == "$bb":
            conns.append([src, dst, "", ["$bb"]]); continue
        x, y = where(src); moves = []
        tx, ty = where(dst)
        if pts and not tail:
            # Wokwi drops the last segment when it is exactly lined up with the target pin;
            # nudge the final waypoint by half a pixel
            lx, ly = pts[-1]
            if abs(lx - tx) < 0.01 and abs(ly - ty) > 0.01: pts = pts[:-1] + [(lx + 0.5, ly)] if len(pts) == 1 or abs(pts[-2][1] - ly) < 0.01 else pts
            elif abs(ly - ty) < 0.01 and abs(lx - tx) > 0.01: pts = pts[:-1] + [(lx, ly + 0.5)] if len(pts) == 1 or abs(pts[-2][0] - lx) < 0.01 else pts
        for (px, py) in pts:
            xs.append(px); ys.append(py)
            if abs(px - x) > 0.01 and abs(py - y) > 0.01: raise SystemExit(f"diagonal waypoint in {w}")
            if abs(py - y) > 0.01: moves.append(f"v{round(py - y, 2):g}")
            if abs(px - x) > 0.01: moves.append(f"h{round(px - x, 2):g}")
            x, y = px, py
        conns.append([src, dst, color, (moves + ["*"] + tail) if (moves or tail) else []])
    out = {"version": 1, "author": "SkillLab", "editor": "wokwi",
           "parts": [{"type": "wokwi-breadboard-half", "id": b.id, "top": b.top, "left": b.left, "attrs": {}} for b in boards.values()]
                    + [{**{k: v for k, v in p.items()}, "attrs": p.get("attrs", {})} for p in parts],
           "connections": conns, "dependencies": {}}
    uno = next(p for p in parts if p["type"] == "wokwi-arduino-uno")
    out["_bounds"] = {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys), "unoLeft": uno["left"], "unoTop": uno["top"]}
    return out
