from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
DEST = ROOT / "webcad_xbf" / "static" / "vendor" / "three"
REQUIRED = {
    "three.core.js": 500_000,
    "three.module.js": 100_000,
    "OrbitControls.js": 5_000,
    "TransformControls.js": 5_000,
    "GLTFLoader.js": 20_000,
    "BufferGeometryUtils.js": 5_000,
}
IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']")

errors: set[str] = set()
for name, minimum in REQUIRED.items():
    path = DEST / name
    if not path.exists():
        errors.add(f"missing {path}")
    elif path.stat().st_size < minimum:
        errors.add(f"truncated {path} ({path.stat().st_size} bytes)")

for path in DEST.glob("*.js"):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "from 'three'" in text or 'from "three"' in text:
        errors.add(f"unresolved bare three import in {path.name}")
    for specifier in IMPORT_RE.findall(text):
        if not specifier.startswith("."):
            continue
        clean_specifier = specifier.split("?", 1)[0].split("#", 1)[0]
        target = (path.parent / clean_specifier).resolve()
        if not target.exists():
            errors.add(f"{path.name} imports missing {specifier}")

module = DEST / "three.module.js"
if module.exists():
    text = module.read_text(encoding="utf-8", errors="replace")
    if "./three.core.js" not in text:
        errors.add("three.module.js does not reference the expected ./three.core.js companion")

loader = DEST / "GLTFLoader.js"
if loader.exists():
    text = loader.read_text(encoding="utf-8", errors="replace")
    if "../utils/BufferGeometryUtils.js" in text:
        errors.add("GLTFLoader.js still points outside the flattened vendor directory")

if errors:
    print("CascadeCAD frontend dependency check failed:", file=sys.stderr)
    for error in sorted(errors):
        print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)

print("CascadeCAD frontend dependencies: OK")
