#!/bin/zsh
# Regenerates assets/renders/ (the 3D figures, 7 steps per example) from content/*.mjs.
# Run it after changing any scene, then `node tools/build.mjs`: the SVG overlay is built from the content files,
# so renders made from an older scene no longer line up with it.
# Needs /Applications/Blender.app and python3 with Pillow. About 12 minutes on an M4.
# Run: tools/render3d.sh [robot drone parking]   (default: all three)
set -e
cd "${0:A:h}/.."
ids=("$@")
(( $#ids )) || ids=(robot drone parking)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
node tools/export3d.mjs "$tmp"
for id in $ids; do
  log="$tmp/$id.log"
  if ! /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 \
      --python tools/blender/render.py -- \
      --scene "$tmp/$id.json" --steps 0,1,2,3,4,5,6 --variant outline --out "$tmp/raw" --scale 2 --samples 96 \
      >"$log" 2>&1; then
    cat "$log"
    exit 1
  fi
  grep '^\[render\]' "$log"
done
python3 tools/blender/compose.py "$tmp/raw" assets/renders
