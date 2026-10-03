"""Renders a SkillLab scene (JSON from tools/export3d.mjs) with Blender Cycles so that it lines up with the SVG drawing.

  Blender -b --factory-startup --python tools/blender/render.py -- \
      --scene robot.json --steps 0,2 --variant plain|outline --out <dir> [--scale 2] [--samples 96]

Writes <out>/<id>-<variant>-s<step>.png (RGBA, transparent background). Run tools/blender/compose.py on <out> afterwards.
Steps: 0 = normal, 1-5 = one slot lit (sense, decide, act, record, send), 6 = the loop parts lit.
outline variant: ink lines (#17181a) on lit parts, light grey lines (#cfcdc8) on the others; at step 0 everything is ink.

Coordinates: content (x, y, z) -> Blender (X, Y, Z) = (y, x, z). The SVG projection is mirror-handed; with this swap a
right-handed Blender camera at (+1, +1, +1) looking at the target reproduces it:
content +x goes screen right-down, +y screen left-down, +z up, and the visible faces are content +x, +y, +z.
"""
import argparse
import json
import math
import os
import sys
import time

import bmesh
import bpy
from mathutils import Matrix, Vector

# ----------------------------------------------------------------------------------------------------------------
# settings
# ----------------------------------------------------------------------------------------------------------------
SLOTS = ['sense', 'decide', 'act', 'record', 'send']      # step 1..5 lights one slot, step 6 lights the loop parts
CAM_DIST = 4000.0
# The whole Blender scene is built at 1 content unit = UNIT Blender units (meshes, camera, catcher alike), so the picture is
# identical. Reason: at coordinates in the thousands Freestyle's visibility test drops stretches of long edges (outlines
# came out in dashes); at 1/100 of that size the lines are complete.
UNIT = 0.01
TO_CAM = Vector((1.0, 1.0, 1.0)).normalized()             # direction towards the camera (same in content and Blender)

BEVEL = 1.2            # box bevel (world units), 2 segments, <= 20 % of the smallest side
GROUND_SHRINK = 1.2    # ground polygons move this far towards their centroid, so tiles show gaps
GROUND_THICK = 2.0     # ground slab, downward
GROUND_LIFT = 0.02     # whole ground, so wall tops / boxes standing at z = 0 never share a visible plane with it
LAYER_LIFT = 0.15      # a ground polygon on top of an earlier one is raised by this per layer
DECAL_THICK = 0.8      # screen, plate: extruded towards the camera
WHEEL_THICK = 10.0     # wheel: extruded away from the camera
FACE_THICK = 2.0       # f-top / f-left / f-right: extruded away from the camera
STOP_THICK = 0.4
LOOP_STRIP = 5.0
LOOP_THICK = 0.4
DETAIL_WIDTH = 1.6
DETAIL_DEPTH = 0.6
DASH, GAP, DASH_WIDTH, DASH_HEIGHT = 22.0, 16.0, 3.0, 0.3

# sun: steep (shadows land roughly under the objects), coming from content -x with a little +y, so shadows fall to +x and
# only the +y side face gets direct sun (the +x face stays in shade, the two visible side faces differ)
SUN_ELEV = math.radians(72.5)
SUN_FROM = math.radians(30)       # horizontal direction of the sun: this far from -x towards +y
SUN_DIR = Vector((-math.cos(SUN_ELEV) * math.cos(SUN_FROM), math.cos(SUN_ELEV) * math.sin(SUN_FROM), math.sin(SUN_ELEV)))
SUN_STRENGTH = 1.35
SUN_ANGLE = math.radians(12)
WORLD_STRENGTH = 0.70
WORLD_COLOR = (1.0, 1.0, 1.0)
EXPOSURE = 0.1        # EV; lit box tops come out near #fdfdf8, side faces near #e2e1dd / #d7d6d1; the lit floor clips to white like the SVG's #fff floor

INK = '#17181a'
INK_OFF = '#cfcdc8'    # outline colour of parts that are not lit (steps 1-6)


def lin(hex_color):
    """'#rrggbb' (sRGB) -> scene-linear RGB tuple"""
    h = hex_color.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


# material role -> state -> (hex, roughness); states: n = step 0, on = active, off = inactive
_PLATE = ('#ffffff', 0.55)
_GROUND = ('#fbfaf8', 0.6)
MATERIALS = {
    'box':       {'n': ('#ecebe7', 0.55), 'on': ('#e4572e', 0.5),  'off': ('#f4f3ef', 0.55)},
    'ground':    {'n': _GROUND,           'on': _GROUND,           'off': _GROUND},
    'screen':    {'n': (INK, 0.25),       'on': (INK, 0.25),       'off': ('#d6d4cf', 0.25)},
    'wheel':     {'n': (INK, 0.8),        'on': (INK, 0.8),        'off': ('#d6d4cf', 0.8)},
    'plate':     {'n': _PLATE,            'on': _PLATE,            'off': _PLATE},
    'detail':    {'n': ('#2e2f33', 0.5),  'on': (INK, 0.5),        'off': ('#d9d7d2', 0.5)},
    'lane-edge': {'n': ('#c4c2bd', 0.6),  'on': ('#c4c2bd', 0.6),  'off': ('#dcdad5', 0.6)},
    'stop':      {'n': ('#a3a5aa', 0.6),  'on': ('#a3a5aa', 0.6),  'off': ('#dcdad5', 0.6)},
    # loop frame: the brief gives no inactive colour; use the same light grey as lane-edge / stop
    'loop':      {'n': ('#b9b7b2', 0.6),  'on': ('#e4572e', 0.5),  'off': ('#dcdad5', 0.6)},
}

# Ground polygons stacked above an earlier one (the drone's landing-pad squares: layer 1 outer, layer 2 inner).
# The hex is the tone they should RENDER with on a lit top face: this scene is exposed so that light albedos clip to white
# (the floor does), so the material colour is that tone divided by the lit factor, else the squares vanish into the slab.
PAD_TONES = ['#efede8', '#f7f6f3']


def lit_factor():
    """radiance of a white upward-facing diffuse surface in open light (world fill + sun), exposure included"""
    return (WORLD_STRENGTH + SUN_STRENGTH / math.pi * math.sin(SUN_ELEV)) * 2.0 ** EXPOSURE


# poly class -> material role (None = not built, it stays in the SVG overlay)
POLY_ROLE = {
    'ground': 'ground', 'screen': 'screen', 'plate': 'plate', 'wheel': 'wheel',
    'f-top': 'box', 'f-left': 'box', 'f-right': 'box',
    'loop': 'loop', 'stop': 'stop', 'net-head': None,
}
LINE_ROLE = {'detail': 'detail', 'lane-edge': 'lane-edge', 'cone': None}


# ----------------------------------------------------------------------------------------------------------------
# small geometry helpers (content space unless the name says otherwise)
# ----------------------------------------------------------------------------------------------------------------
def B(p):
    """content point/vector -> Blender"""
    return Vector((p[1], p[0], p[2]))


def newell(pts):
    n = Vector((0.0, 0.0, 0.0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-9 else Vector((0.0, 0.0, 1.0))


def facing_camera(n):
    return n if n.dot(TO_CAM) >= 0 else -n


def centroid(pts):
    c = Vector((0.0, 0.0, 0.0))
    for p in pts:
        c += p
    return c / len(pts)


def inside_xy(pt, poly):
    x, y, inside = pt.x, pt.y, False
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a.y > y) != (b.y > y) and x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x:
            inside = not inside
    return inside


def prism(pts, ext):
    """closed prism: polygon pts (content) swept by ext (content vector). Returns a bmesh in Blender coordinates."""
    bm = bmesh.new()
    base = [bm.verts.new(B(p)) for p in pts]
    top = [bm.verts.new(B(p + ext)) for p in pts]
    bm.faces.new(base)
    bm.faces.new(list(reversed(top)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([base[i], base[j], top[j], top[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def strip(a, b, n, width, depth, off=0.0):
    """flat bar from a to b (content), `width` across (in the plane perpendicular to n), `depth` along n, starting `off` along n"""
    d = (b - a)
    d.normalize()
    w = n.cross(d)
    w.normalize()
    q = [a + w * (-width / 2) + n * off, b + w * (-width / 2) + n * off, b + w * (width / 2) + n * off, a + w * (width / 2) + n * off]
    return prism(q, n * depth)


def box_bm(box, bevel=True):
    x0, x1, y0, y1, z0, z1 = box
    lo, hi = Vector((y0, x0, z0)), Vector((y1, x1, z1))        # Blender coordinates
    size = hi - lo
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((lo.x + (v.co.x + 0.5) * size.x, lo.y + (v.co.y + 0.5) * size.y, lo.z + (v.co.z + 0.5) * size.z))
    r = min(BEVEL, 0.2 * min(size.x, size.y, size.z))
    if bevel and r > 1e-4:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=r, offset_type='OFFSET', profile=0.5, segments=2,
                        affect='EDGES', clamp_overlap=True)
    return bm


# ----------------------------------------------------------------------------------------------------------------
# arguments
# ----------------------------------------------------------------------------------------------------------------
def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(prog='render.py')
    ap.add_argument('--scene', required=True, help='JSON written by tools/export3d.mjs')
    ap.add_argument('--steps', default='0', help='comma list of steps, 0 = normal, 1-5 = one slot, 6 = loop')
    ap.add_argument('--variant', choices=['plain', 'outline'], default='outline')
    ap.add_argument('--out', required=True)
    ap.add_argument('--scale', type=float, default=2.0, help='output pixels per drawing unit')
    ap.add_argument('--samples', type=int, default=96)
    a = ap.parse_args(argv)
    a.steps = [int(s) for s in a.steps.split(',') if s.strip() != '']
    for s in a.steps:
        if not 0 <= s <= 6:
            ap.error('steps must be 0..6')
    return a


# ----------------------------------------------------------------------------------------------------------------
# scene
# ----------------------------------------------------------------------------------------------------------------
class Scene3D:
    def __init__(self, data):
        self.data = data
        self.sc = bpy.context.scene
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        self.line_on = self._collection('lines-ink')    # outlined objects whose lines are ink (lit parts; everything at step 0)
        self.line_off = self._collection('lines-grey')  # outlined objects whose lines are light grey (parts not lit)
        self.flat = self._collection('flat')            # ground, lane edges, stop line, loop frame: no outlines
        self.aux = self._collection('aux')              # shadow catcher
        self.items = []                                 # {obj, role, slot, loop, outlined}
        self.linesets = []                              # (Freestyle line set, its collection), outline variant only
        self.skipped = {}
        self.mats = {}
        self.zmin = 1e9

    def _collection(self, name):
        c = bpy.data.collections.new(name)
        self.sc.collection.children.link(c)
        return c

    # -------- materials --------
    def material(self, role, state):
        if role.startswith('pad'):
            state = 'n'                                 # the same in every step
        key = (role, state)
        if key not in self.mats:
            if role.startswith('pad'):
                hx, rough = PAD_TONES[int(role[3:]) - 1], 0.6
                base = tuple(min(1.0, c / lit_factor()) for c in lin(hx))
            else:
                hx, rough = MATERIALS[role][state]
                base = lin(hx)
            m = bpy.data.materials.new(f'{role}-{state}')
            m.use_nodes = True
            b = m.node_tree.nodes['Principled BSDF']
            b.inputs['Base Color'].default_value = (*base, 1.0)
            b.inputs['Roughness'].default_value = rough
            self.mats[key] = m
        return self.mats[key]

    # -------- objects --------
    def add(self, name, bm, role, slot, loop, flat=False):
        me = bpy.data.meshes.new(name)
        for v in bm.verts:
            self.zmin = min(self.zmin, v.co.z)          # content units
        bm.transform(Matrix.Scale(UNIT, 4))
        bm.to_mesh(me)
        bm.free()
        me.materials.append(self.material(role, 'n'))
        ob = bpy.data.objects.new(name, me)
        (self.flat if flat else self.line_on).objects.link(ob)
        self.items.append({'obj': ob, 'role': role, 'slot': slot, 'loop': bool(loop), 'outlined': not flat})
        return ob

    def build(self):
        d = self.data
        boxes = d['boxes']
        for i, b in enumerate(boxes):
            self.add(f'box{i}-{b["part"]}', box_bm(b['box']), 'box', b['slot'], b['loop'])

        polys = sorted(d['polys'], key=lambda p: p['id'])
        grounds = []
        for p in polys:
            cls = p['cls']
            if cls not in POLY_ROLE:
                self.skipped[cls] = self.skipped.get(cls, 0) + 1
                print(f'[render] WARNING: unknown poly class {cls!r} skipped')
                continue
            role = POLY_ROLE[cls]
            if role is None:
                self.skipped[cls] = self.skipped.get(cls, 0) + 1
                continue
            pts = [Vector(q) for q in p['pts']]
            name = f'poly{p["id"]}-{cls}'
            nrm = facing_camera(newell(pts))
            if cls == 'ground':
                layer = sum(1 for g in grounds if abs(g[0][0].z - pts[0].z) < 1e-3 and inside_xy(centroid(pts), g[0]))
                grounds.append((pts, p))
                if layer > 0:
                    role = f'pad{min(layer, len(PAD_TONES))}'
                c = centroid(pts)
                shrunk = []
                for q in pts:
                    toward = c - q
                    shrunk.append(q + toward.normalized() * min(GROUND_SHRINK, toward.length * 0.5) if toward.length > 1e-9 else q)
                lift = Vector((0, 0, GROUND_LIFT + LAYER_LIFT * layer))
                bm = prism([q + lift for q in shrunk], Vector((0, 0, -GROUND_THICK)))
                self.add(name, bm, role, p['slot'], p['loop'], flat=True)
            elif cls in ('screen', 'plate'):
                self.add(name, prism(pts, nrm * DECAL_THICK), role, p['slot'], p['loop'])
            elif cls == 'wheel':
                self.add(name, prism(pts, -nrm * WHEEL_THICK), role, p['slot'], p['loop'])
            elif cls in ('f-top', 'f-left', 'f-right'):
                self.add(name, prism(pts, -nrm * FACE_THICK), role, p['slot'], p['loop'])
            elif cls == 'stop':
                self.add(name, prism(pts, nrm * STOP_THICK), role, p['slot'], p['loop'], flat=True)
            elif cls == 'loop':
                xs, ys, z = [q.x for q in pts], [q.y for q in pts], pts[0].z
                x0, x1, y0, y1, s = min(xs), max(xs), min(ys), max(ys), LOOP_STRIP
                for k, bx in enumerate([(x0, x1, y0, y0 + s), (x0, x1, y1 - s, y1),
                                        (x0, x0 + s, y0 + s, y1 - s), (x1 - s, x1, y0 + s, y1 - s)]):
                    self.add(f'{name}-{k}', box_bm([bx[0], bx[1], bx[2], bx[3], z, z + LOOP_THICK], bevel=False),
                             role, p['slot'], p['loop'], flat=True)

        for l in sorted(d['lines'], key=lambda q: q['id']):
            cls = l['cls']
            role = LINE_ROLE.get(cls, None)
            if role is None:
                self.skipped[cls] = self.skipped.get(cls, 0) + 1
                if cls not in LINE_ROLE:
                    print(f'[render] WARNING: unknown line class {cls!r} skipped')
                continue
            a, b = Vector(l['a']), Vector(l['b'])
            if cls == 'detail':
                host = boxes[l['host']]['box'] if l.get('host') is not None else None
                self.add(f'line{l["id"]}-detail', strip(a, b, self.detail_normal(a, b, host), DETAIL_WIDTH, DETAIL_DEPTH),
                         role, l['slot'], l['loop'])
            elif cls == 'lane-edge':
                length = (b - a).length
                dirv = (b - a).normalized()
                k, s = 0, 0.0
                while s < length - 1e-6:
                    e = min(s + DASH, length)
                    self.add(f'line{l["id"]}-dash{k}', strip(a + dirv * s, a + dirv * e, Vector((0, 0, 1)), DASH_WIDTH, DASH_HEIGHT),
                             role, l['slot'], l['loop'], flat=True)
                    k, s = k + 1, s + DASH + GAP

    @staticmethod
    def detail_normal(a, b, host):
        """a detail line sits ~0.3 in front of a visible (+x, +y or +z) face of its host box: that face's normal"""
        d = (b - a).normalized()
        axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
        cand = []
        for k in range(3):
            if abs(d[k]) > 1e-6:
                continue
            if host is not None:
                excess = a[k] - host[2 * k + 1]
                if -1e-6 <= excess <= 1.0:
                    cand.append((excess, k))
            else:
                cand.append((0.0, k))
        if not cand:
            cand = [(0.0, k) for k in range(3) if abs(d[k]) < 1e-6]
            print('[render] WARNING: detail line without a matching host face, guessing')
        return axes[min(cand)[1]]

    # -------- step -> materials --------
    def apply_step(self, step):
        for it in self.items:
            if step == 0:
                state = 'n'
            elif step <= 5:
                state = 'on' if it['slot'] == SLOTS[step - 1] else 'off'
            else:
                state = 'on' if it['loop'] else 'off'
            ob = it['obj']
            ob.data.materials[0] = self.material(it['role'], state)
            if it['outlined']:                     # ink lines on lit parts, light grey lines on the rest (the outline variant's two line sets)
                want, other = (self.line_off, self.line_on) if state == 'off' else (self.line_on, self.line_off)
                if ob.name in other.objects:
                    other.objects.unlink(ob)
                if ob.name not in want.objects:
                    want.objects.link(ob)
        for ls, coll in self.linesets:             # a line set without objects (grey at step 0) is switched off
            ls.show_render = len(coll.objects) > 0

    # -------- camera, light, catcher --------
    def setup_camera(self, scale):
        d = self.data
        w, h, OX, OY, S = d['w'], d['h'], d['OX'], d['OY'], d['S']
        K = math.cos(math.radians(30))
        cx, cy = w / 2 - OX, h / 2 - OY           # centre of the viewBox, in projector space (no offset)
        a, b = cx / (K * S), 2 * cy / S           # a = x - y, b = x + y   (z = 0)
        x, y = (a + b) / 2, (b - a) / 2
        target = Vector((y, x, 0.0))              # Blender
        cam_data = bpy.data.cameras.new('cam')
        cam_data.type = 'ORTHO'
        cam_data.sensor_fit = 'HORIZONTAL'
        cam_data.ortho_scale = w / (S * math.sqrt(1.5)) * UNIT
        cam_data.clip_start = 1.0 * UNIT
        cam_data.clip_end = 20000.0 * UNIT
        cam = bpy.data.objects.new('cam', cam_data)
        self.sc.collection.objects.link(cam)
        cam.location = (target + Vector((1, 1, 1)) * CAM_DIST) * UNIT
        cam.rotation_euler = (target * UNIT - cam.location).to_track_quat('-Z', 'Y').to_euler()
        self.sc.camera = cam
        r = self.sc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = round(w * scale), round(h * scale), 100
        self.target = target

    def setup_light(self):
        sun_data = bpy.data.lights.new('sun', 'SUN')
        sun_data.energy = SUN_STRENGTH
        sun_data.angle = SUN_ANGLE
        sun = bpy.data.objects.new('sun', sun_data)
        self.sc.collection.objects.link(sun)
        to_sun = B(SUN_DIR)                                    # Blender direction towards the sun
        sun.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
        world = bpy.data.worlds.new('fill')
        world.use_nodes = True
        bg = world.node_tree.nodes['Background']
        bg.inputs['Color'].default_value = (*WORLD_COLOR, 1.0)
        bg.inputs['Strength'].default_value = WORLD_STRENGTH
        self.sc.world = world

    def setup_catcher(self):
        d = self.data
        z = self.zmin - 0.05
        c = self.target
        R = 6.0 * max(d['w'], d['h'])
        me = bpy.data.meshes.new('catcher')
        quad = [(c.x - R, c.y - R, z), (c.x + R, c.y - R, z), (c.x + R, c.y + R, z), (c.x - R, c.y + R, z)]
        me.from_pydata([(x * UNIT, y * UNIT, zz * UNIT) for x, y, zz in quad], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new('catcher', me)
        self.aux.objects.link(ob)
        ob.is_shadow_catcher = True
        self.catcher_z = z


def setup_render(args):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cs = sc.cycles
    cs.samples = args.samples
    cs.use_denoising = True
    cs.denoiser = 'OPENIMAGEDENOISE'
    cs.device = 'GPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.refresh_devices()
    for dev in prefs.devices:
        # every Metal device on; the CPU entry stays off (CPU+GPU hybrid measured 40 s per image vs 24 s on the GPU alone)
        dev.use = dev.type != 'CPU'
    print('[render] devices:', ', '.join(f'{dev.name} [{dev.type}] use={dev.use}' for dev in prefs.devices),
          '| GPU active:', prefs.has_active_device())
    r = sc.render
    r.film_transparent = True
    r.filter_size = 1.0
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGBA'
    r.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = EXPOSURE
    sc.view_settings.gamma = 1.0


def setup_outline(scene3d, scale):
    """Freestyle: lines on silhouettes and creases of everything except the flat ground-level shapes.
    Two line sets chosen by collection: lit parts get ink lines, the others light grey lines. The first line set in the list is
    drawn on top of the later ones, so ink goes first (else grey caps would nick the ink outlines where parts touch)."""
    sc = bpy.context.scene
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = 'ABSOLUTE'
    sc.render.line_thickness = 1.0
    vl = sc.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(140)       # 90 deg edges and the middle edge of a 2-segment bevel (135 deg), not its 157.5 deg ones
    for k, (name, collection, color) in enumerate([('ink', scene3d.line_on, INK), ('grey', scene3d.line_off, INK_OFF)]):
        ls = fs.linesets[0] if k == 0 else fs.linesets.new(name)
        ls.name = name
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = True
        ls.select_contour = False
        ls.select_external_contour = False
        ls.select_material_boundary = False
        ls.select_edge_mark = False
        ls.select_by_visibility = True
        ls.visibility = 'VISIBLE'
        ls.select_by_collection = True
        ls.collection = collection
        style = bpy.data.linestyles.new(name)
        style.color = lin(color)
        style.alpha = 1.0
        style.thickness = 1.25 * scale            # 2.5 px at scale 2
        style.thickness_position = 'CENTER'
        style.caps = 'ROUND'
        ls.linestyle = style
        scene3d.linesets.append((ls, collection))


def main():
    args = parse_args()
    with open(args.scene, encoding='utf-8') as f:
        data = json.load(f)
    sid = data.get('id') or os.path.splitext(os.path.basename(args.scene))[0]
    os.makedirs(args.out, exist_ok=True)

    setup_render(args)
    s3 = Scene3D(data)
    s3.build()
    s3.setup_camera(args.scale)
    s3.setup_light()
    s3.setup_catcher()
    if args.variant == 'outline':
        setup_outline(s3, args.scale)
    n_roles = {}
    for it in s3.items:
        n_roles[it['role']] = n_roles.get(it['role'], 0) + 1
    print(f'[render] {sid}: {len(s3.items)} objects {n_roles}; not built (stay in the SVG overlay): {s3.skipped}')
    print(f'[render] {sc_res()} px, scale {args.scale}, samples {args.samples}, variant {args.variant}, catcher z {s3.catcher_z:.2f}')

    for step in args.steps:
        s3.apply_step(step)
        path = os.path.join(args.out, f'{sid}-{args.variant}-s{step}.png')
        bpy.context.scene.render.filepath = path
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'[render] wrote {path} in {time.time() - t0:.1f} s', flush=True)


def sc_res():
    r = bpy.context.scene.render
    return f'{r.resolution_x}x{r.resolution_y}'


main()
