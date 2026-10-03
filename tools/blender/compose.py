"""Turns the RGBA renders of tools/blender/render.py into the web images.

  python3 tools/blender/compose.py <rawDir> <outDir> [--variant outline] [--quality 80]

For every <id>-<variant>-s<n>.png in <rawDir> (a scale-2 RGBA render) writes into <outDir>
  <id>-s<n>@2x.webp   the render itself
  <id>-s<n>.webp      the same, LANCZOS-downscaled to half size (1x)
Both are lossy WebP with alpha and a transparent background: they are NOT composited over the paper, the page shows through.

Shadow fix. Shadows that fall on the shadow-catcher are black with partial alpha, and the browser blends them in sRGB, which
makes them much darker than the linear-light shadows on the floor tiles. For those shadow-only pixels (RGB ~ 0, 0 < alpha < 1)
alpha a is replaced by  a' = 1 - srgb(bg_lin * (1 - a)) / bg_srgb  with bg = the page colour #fbfaf8, so the sRGB blend over
the page gives the linear-light result. Pixels that carry colour (object edges, outlines) are left alone.
Two small adjustments, also only on those shadow-only pixels, so the image does not show as a box on the page:
the faint ambient fog of the catcher (alpha 1-5 of 255, out to the borders) is cut by ALPHA_FLOOR levels, and alpha fades to 0
over FEATHER_PX at the image border (shadows are cut by the viewBox there and would leave a straight edge).
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PAPER = (251, 250, 248)            # the page background, #fbfaf8
SHADOW_RGB_MAX = 3                 # "RGB ~ 0": the catcher writes exactly black; anything with colour is an object
ALPHA_FLOOR = 2.0                  # levels of 255 taken off the corrected shadow alpha
FEATHER_PX = 32                    # at 2x: shadow alpha fades to 0 over this distance from the image border
LIMIT_KB = {'@2x': 350, '1x': 120}
NAME = re.compile(r'^(?P<id>.+)-(?P<variant>plain|outline)-s(?P<step>[0-6])\.png$')


def to_lin(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def to_srgb(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


def fix_shadow_alpha(rgba):
    """rgba: uint8 array (h, w, 4). Returns (copy with corrected shadow alpha, number of pixels changed)."""
    a = rgba[..., 3]
    shadow = (a > 0) & (a < 255) & (rgba[..., :3].max(axis=-1) <= SHADOW_RGB_MAX)
    af = a[shadow].astype(np.float64) / 255.0
    new = np.zeros_like(af)
    for c in PAPER:                                            # the three channels differ by <1 %, use their mean
        bg = c / 255.0
        new += 1.0 - to_srgb(to_lin(bg) * (1.0 - af)) / bg
    new = np.maximum(new / len(PAPER) * 255.0 - ALPHA_FLOOR, 0.0)
    ys, xs = np.nonzero(shadow)
    h, w = a.shape
    t = np.clip(np.minimum.reduce([xs, w - 1 - xs, ys, h - 1 - ys]) / FEATHER_PX, 0.0, 1.0)
    new *= t * t * (3.0 - 2.0 * t)                             # smoothstep: 0 at the border, 1 from FEATHER_PX inwards
    out = rgba.copy()
    out[..., 3][shadow] = np.clip(np.rint(new), 0, 255).astype(np.uint8)
    return out, int(shadow.sum())


def save_webp(im, path, quality):
    im.save(path, 'WEBP', quality=quality, method=6, alpha_quality=100)
    corner = Image.open(path).convert('RGBA').getpixel((0, 0))
    assert corner[3] == 0, f'{path.name}: top-left pixel is not transparent: {corner}'
    return path.stat().st_size / 1024


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('raw_dir')
    ap.add_argument('out_dir')
    ap.add_argument('--variant', choices=['plain', 'outline'], default='outline')
    ap.add_argument('--quality', type=int, default=80, help='lossy WebP quality (alpha is kept lossless)')
    args = ap.parse_args()

    raw, out = Path(args.raw_dir), Path(args.out_dir)
    if not raw.is_dir():
        sys.exit(f'not a directory: {raw}')
    out.mkdir(parents=True, exist_ok=True)

    files = []
    for f in sorted(raw.glob('*.png')):
        m = NAME.match(f.name)
        if m and m['variant'] == args.variant:
            files.append((m['id'], int(m['step']), f))
    if not files:
        sys.exit(f'no <id>-{args.variant}-s<n>.png renders in {raw}')

    over = []
    for sid, step, src in files:
        with Image.open(src) as im:
            if im.mode != 'RGBA':
                sys.exit(f'{src.name}: mode {im.mode}, expected an RGBA render')
            rgba = np.asarray(im).copy()
        w2, h2 = rgba.shape[1], rgba.shape[0]
        if w2 % 2 or h2 % 2:
            sys.exit(f'{src.name}: {w2}x{h2} is not a scale-2 render (odd size)')
        fixed, n = fix_shadow_alpha(rgba)
        big = Image.fromarray(fixed)                                  # (h, w, 4) uint8 -> RGBA
        small = big.resize((w2 // 2, h2 // 2), Image.LANCZOS)      # Pillow resizes RGBA with premultiplied alpha

        p2, p1 = out / f'{sid}-s{step}@2x.webp', out / f'{sid}-s{step}.webp'
        kb2, kb1 = save_webp(big, p2, args.quality), save_webp(small, p1, args.quality)
        flag = []
        if kb2 > LIMIT_KB['@2x']:
            flag.append('2x over target')
        if kb1 > LIMIT_KB['1x']:
            flag.append('1x over target')
        over += flag
        print(f'{src.name:26s} -> {p2.name} {w2}x{h2} {kb2:6.1f} KB | {p1.name} {w2 // 2}x{h2 // 2} {kb1:6.1f} KB'
              f'  (shadow alpha fixed on {n} px){"  <-- " + ", ".join(flag) if flag else ""}')
    print(f'{len(files)} render(s) -> {out}' + (f'; {len(over)} size target(s) missed' if over else '; all within the size targets'))


if __name__ == '__main__':
    main()
