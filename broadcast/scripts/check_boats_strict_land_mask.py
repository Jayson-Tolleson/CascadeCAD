#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from scripts._venv_bootstrap import ensure_project_venv
    ensure_project_venv(__file__)
except Exception:
    pass

from app.schemas.scene import BBox
from app.services.boat_generator import generate_viewport_boats
from app.services.marine_land_mask import marine_mask_for_boat_point


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise SystemExit(message)


def main() -> None:
    # Known dry land inside the common SoCal viewport must reject boats.
    oc_land = marine_mask_for_boat_point(-117.90, 33.80)
    assert_true(not oc_land.get("should_render_boat"), f"OC mainland accepted boat: {oc_land}")
    assert_true(oc_land.get("matched_land"), f"OC mainland did not report matched land: {oc_land}")

    # Harbors/bays must still punch through the strict visual land mask.
    sd_bay = marine_mask_for_boat_point(-117.17, 32.70)
    assert_true(bool(sd_bay.get("should_render_boat")), f"San Diego Bay rejected boat: {sd_bay}")
    assert_true(sd_bay.get("matched_water") == "san_diego_bay", f"San Diego Bay did not use harbor override: {sd_bay}")

    # Islands must reject land points even when the wider nearshore tile remains
    # queryable for ocean data.
    catalina = marine_mask_for_boat_point(-118.45, 33.40)
    assert_true(not catalina.get("should_render_boat"), f"Catalina land accepted boat: {catalina}")

    open_water = marine_mask_for_boat_point(-119.00, 33.50)
    assert_true(bool(open_water.get("should_render_boat")), f"Open channel water rejected boat: {open_water}")

    socal = generate_viewport_boats(BBox(west=-125, south=32, east=-117, north=38), count=12)
    assert_true(socal.get("source") == "viewport_seeded_boat_entities_strict_land_masked", f"Unexpected source: {socal.get('source')}")
    assert_true(socal.get("marine_point_mask", {}).get("point_level_mask") is True, f"Missing point mask: {socal}")
    for boat in socal.get("boats", []):
        mask = marine_mask_for_boat_point(boat["lon"], boat["lat"])
        assert_true(bool(mask.get("should_render_boat")), f"Generated boat failed strict mask: {boat} {mask}")
        meta = boat.get("safety_metadata", {})
        assert_true(meta.get("boat_mask_checked") is True, f"Boat lacks mask metadata: {boat}")

    phoenix = generate_viewport_boats(BBox(west=-112.3, south=33.2, east=-111.7, north=33.8), count=12)
    assert_true(phoenix.get("count") == 0, f"Phoenix generated boats: {phoenix}")

    print("✓ boats strict land-mask checks passed")


if __name__ == "__main__":
    main()
