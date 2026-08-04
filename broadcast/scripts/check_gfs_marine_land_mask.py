#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Server-friendly: when called as `python3 scripts/this_check.py`, jump into
# the project venv created by scripts/install.sh before importing app deps.
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(Path(__file__).resolve().parents[1])
except Exception:
    pass

from app.schemas.scene import BBox
from app.services.marine_land_mask import marine_mask_for_bbox
from app.providers.rtofs_ncep import get_rtofs_provider
from app.services.boat_generator import generate_viewport_boats


def expect(name: str, bbox: BBox, should_query: bool, contains: str | None = None) -> None:
    mask = marine_mask_for_bbox(bbox)
    if bool(mask.get("should_query_ocean")) != should_query:
        raise SystemExit(f"{name}: expected should_query_ocean={should_query}, got {mask}")
    if contains and contains not in " ".join(mask.get("matched_water", []) + [mask.get("classification", ""), mask.get("reason", "")]):
        raise SystemExit(f"{name}: expected diagnostic to contain {contains!r}, got {mask}")


def main() -> None:
    # Obvious inland bbox should not trigger future SST/RTOFS/chlorophyll calls.
    phoenix = BBox(west=-112.3, south=33.2, east=-111.7, north=33.8)
    expect("phoenix_interior_landlocked", phoenix, False, "landlocked")
    frame, status = get_rtofs_provider().fetch_ocean(phoenix)
    mask = frame.metadata.get("marine_land_mask", {})
    if mask.get("should_query_ocean") is not False:
        raise SystemExit(f"RTOFS provider did not expose landlocked mask: {frame.metadata}")
    if "marine land mask skipped" not in (status.error or ""):
        raise SystemExit(f"RTOFS provider did not skip using mask: {status.model_dump(mode='json')}")
    boats = generate_viewport_boats(phoenix, count=6)
    if boats.get("count") != 0:
        raise SystemExit(f"Landlocked boat generation should return zero boats: {boats}")

    # Protected waters must remain queryable even inside tight city/coast bboxes.
    expect("san_diego_bay", BBox(west=-117.25, south=32.62, east=-117.10, north=32.76), True, "san_diego_bay")
    expect("la_long_beach_harbor", BBox(west=-118.30, south=33.70, east=-118.05, north=33.83), True, "los_angeles")
    expect("san_francisco_bay", BBox(west=-122.55, south=37.45, east=-121.80, north=38.10), True, "san_francisco")
    expect("chesapeake_bay", BBox(west=-77.2, south=37.0, east=-75.7, north=39.4), True, "chesapeake")
    expect("open_pacific", BBox(west=-123.0, south=32.0, east=-121.0, north=34.0), True)

    print({"ok": True, "check": "gfs_marine_land_mask_harbors_bays_sst_call_gate"})


if __name__ == "__main__":
    main()
