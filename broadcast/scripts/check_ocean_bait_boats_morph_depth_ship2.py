from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text()

def assert_contains(path: str, needle: str) -> None:
    text = read(path)
    assert needle in text, f"missing {needle!r} in {path}"

assert_contains("app/services/ocean_features.py", "_stable_cell_id")
assert_contains("app/services/ocean_features.py", "transparent_orange_school_shell")
assert_contains("frontend/src/renderer/baitSchoolMorph.ts", "BaitSchoolMorphController")
assert_contains("frontend/src/renderer/baitSchoolMorph.ts", "mirror silver/white bait particle")
assert_contains("frontend/src/renderer/boatLegacyVisual.ts", "SHIP2_MODEL_SRC")
assert_contains("frontend/src/renderer/boatLegacyVisual.ts", "boatOceanHazardPolygons")
assert_contains("frontend/src/main.ts", "lastGoodOceanPatch")
assert_contains("frontend/src/main.ts", "retaining/advection-morphing")
assert (ROOT / "frontend/public/models/ship2.gltf").exists(), "ship2.gltf not copied into public models"
print("ok: ocean bait/boats morph depth ship2 contract present")
