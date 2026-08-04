#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
checks = {
    "bait legacy adapter": root / "frontend/src/renderer/baitLegacyVisual.ts",
    "boat legacy adapter": root / "frontend/src/renderer/boatLegacyVisual.ts",
    "main": root / "frontend/src/main.ts",
    "css": root / "frontend/src/styles/app.css",
}
missing = [name for name, path in checks.items() if not path.exists()]
if missing:
    raise SystemExit(f"missing merge files: {missing}")
main = checks["main"].read_text()
required_main = [
    "buildMergedBaitFeatures",
    "baitLegacyPolygons",
    "baitLegacyDriftLines",
    "buildMergedBoatFeatures",
    "boatLegacyWakeLines",
    "drawBoats(cachedBoats);",
]
for needle in required_main:
    if needle not in main:
        raise SystemExit(f"missing main wiring: {needle}")
for path, needles in {
    checks["bait legacy adapter"]: ["BaitRenderFeature", "ocean-feature-cluster", "baitLegacySummary"],
    checks["boat legacy adapter"]: ["BoatRenderFeature", "bow-forward", "boatLegacySummary"],
    checks["css"]: ["legacy-bait-glow-marker", "legacy-boat-marker"],
}.items():
    text = path.read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"missing {needle} in {path}")
print("bait/boats renderer merge wiring ok")
