#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="$ROOT/webcad_xbf/static/vendor/three"
VERSION="0.180.0"
mkdir -p "$DEST"
PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN="$(command -v python3)"; fi
if "$PYTHON_BIN" "$ROOT/scripts/check_frontend.py" "$ROOT" >/dev/null 2>&1; then
  printf 'Existing pinned Three.js dependency set is valid in %s\n' "$DEST"
  exit 0
fi
sources=(
  "https://unpkg.com/three@${VERSION}"
  "https://cdn.jsdelivr.net/npm/three@${VERSION}"
  "https://raw.githubusercontent.com/mrdoob/three.js/r180"
)

fetch() {
  local relative="$1"
  local destination="$2"
  local temporary="${destination}.download"
  local source url
  rm -f "$temporary"
  for source in "${sources[@]}"; do
    url="${source}/${relative}"
    if curl -fL --retry 3 --retry-all-errors --connect-timeout 20 \
      "$url" -o "$temporary"; then
      if [[ -s "$temporary" ]]; then
        mv -f "$temporary" "$destination"
        return 0
      fi
    fi
    rm -f "$temporary"
  done
  echo "ERROR: unable to download pinned Three.js ${VERSION} file: ${relative}" >&2
  return 1
}

fetch "build/three.core.js" "$DEST/three.core.js"
fetch "build/three.module.js" "$DEST/three.module.js"
fetch "examples/jsm/controls/OrbitControls.js" "$DEST/OrbitControls.js"
fetch "examples/jsm/controls/TransformControls.js" "$DEST/TransformControls.js"
fetch "examples/jsm/loaders/GLTFLoader.js" "$DEST/GLTFLoader.js"
fetch "examples/jsm/utils/BufferGeometryUtils.js" "$DEST/BufferGeometryUtils.js"

# Three.js r180 splits the ESM build: three.module.js imports ./three.core.js.
# Both files must be colocated. The examples use the npm bare module name. The browser build is self-hosted,
# so point every addon at the colocated core module.
sed -i "s#from 'three'#from './three.module.js'#g" \
  "$DEST/OrbitControls.js" "$DEST/TransformControls.js" \
  "$DEST/GLTFLoader.js" "$DEST/BufferGeometryUtils.js"
sed -i 's#from "three"#from "./three.module.js"#g' \
  "$DEST/OrbitControls.js" "$DEST/TransformControls.js" \
  "$DEST/GLTFLoader.js" "$DEST/BufferGeometryUtils.js"

# GLTFLoader is flattened into this directory, so its utility import must be
# flattened too. This missing transitive dependency caused editor startup to
# stop before any JavaScript executed in CascadeCAD 0.2.0.
sed -i \
  -e "s#from '../utils/BufferGeometryUtils.js'#from './BufferGeometryUtils.js'#g" \
  -e 's#from "../utils/BufferGeometryUtils.js"#from "./BufferGeometryUtils.js"#g' \
  "$DEST/GLTFLoader.js"


# Version every transitive ES-module import so browsers cannot reuse an older,
# incomplete module graph after an in-place CascadeCAD upgrade.
python3 - "$DEST" <<'PYVENDOR'
from pathlib import Path
import sys
root = Path(sys.argv[1])
version = "0.7.0"
replacements = {
    "three.module.js": [("./three.core.js", f"./three.core.js?v={version}")],
    "OrbitControls.js": [("./three.module.js", f"./three.module.js?v={version}")],
    "TransformControls.js": [("./three.module.js", f"./three.module.js?v={version}")],
    "BufferGeometryUtils.js": [("./three.module.js", f"./three.module.js?v={version}")],
    "GLTFLoader.js": [
        ("./three.module.js", f"./three.module.js?v={version}"),
        ("./BufferGeometryUtils.js", f"./BufferGeometryUtils.js?v={version}"),
    ],
}
for name, pairs in replacements.items():
    path = root / name
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
PYVENDOR

"$PYTHON_BIN" "$ROOT/scripts/check_frontend.py" "$ROOT"
printf 'Vendored and verified Three.js %s in %s\n' "$VERSION" "$DEST"
