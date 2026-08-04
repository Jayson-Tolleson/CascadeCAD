from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import math
from typing import Callable, Iterable, TypeVar

from app.schemas.scene import BBox

T = TypeVar("T")


def tile_id_for_bbox(bbox: BBox, lod: int = 0) -> str:
    return f"lod{lod}:{bbox.west:.2f},{bbox.south:.2f},{bbox.east:.2f},{bbox.north:.2f}"


def default_field_bbox() -> BBox:
    return BBox(west=-125.0, south=32.0, east=-117.0, north=38.0)


@dataclass(frozen=True)
class FieldTile:
    """Stable lon/lat tile used by the backend field engine.

    The important rule: tile boundaries are snapped to a world lattice.  A viewport can
    move or zoom, but a cloud/ocean value that lives in a given lon/lat tile keeps the
    same tile id and does not get re-invented from viewport-normalized coordinates.
    """

    id: str
    bbox: BBox
    row: int
    col: int
    tile_deg: float


def _normalize_lon(value: float) -> float:
    # Keep values in [-180, 180).  The app intentionally avoids dateline-crossing bbox
    # streaming for now; this protects tile math from transient camera values.
    value = ((value + 180.0) % 360.0) - 180.0
    if value == -180.0:
        return 180.0
    return value


def _safe_bbox(bbox: BBox) -> BBox:
    west = _normalize_lon(bbox.west)
    east = _normalize_lon(bbox.east)
    south = max(-84.5, min(84.5, bbox.south))
    north = max(-84.5, min(84.5, bbox.north))
    if north < south:
        south, north = north, south
    # Do not pass dateline-crossing bboxes into this first-pass tile planner.  The
    # frontend guard should prevent them; this backend guard retains a sane regional box.
    if east <= west:
        center = _normalize_lon((west + east) / 2.0)
        half = min(12.0, max(2.0, abs(east - west) / 2.0))
        west = max(-179.9, center - half)
        east = min(179.9, center + half)
    return BBox(west=west, south=south, east=east, north=north)


def _nice_tile_deg(raw: float) -> float:
    """Choose a globally aligned tile size that keeps a bbox near 8x8 tiles.

    Values are intentionally degree-based and snapped to a small set of fixed sizes so
    requests for nearby/zoomed bboxes reuse the same world tile lattice instead of
    inventing arbitrary subdivisions.
    """

    candidates = [0.125, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0]
    for candidate in candidates:
        if raw <= candidate:
            return candidate
    return candidates[-1]


def stable_tile_plan(
    bbox: BBox,
    max_axis_tiles: int = 8,
    max_tiles: int = 64,
    min_tile_deg: float = 0.25,
) -> tuple[list[FieldTile], dict]:
    """Return stable world-lattice tiles covering bbox, capped around 8x8.

    The external stream still represents one viewport.  Internally, this planner creates
    tile requests aligned to absolute lon/lat degrees.  That means clouds and ocean
    structures can remain coherent across pan/zoom while the backend parallelizes work.
    """

    safe = _safe_bbox(bbox)
    width = max(0.01, safe.east - safe.west)
    height = max(0.01, safe.north - safe.south)
    tile_deg = max(min_tile_deg, _nice_tile_deg(max(width, height) / max(1, max_axis_tiles)))

    # Increase tile size until the tile count is bounded.  This is the runtime safety
    # valve for unexpectedly wide requests.
    while True:
        west_idx = math.floor(safe.west / tile_deg)
        east_idx = math.ceil(safe.east / tile_deg) - 1
        south_idx = math.floor(safe.south / tile_deg)
        north_idx = math.ceil(safe.north / tile_deg) - 1
        count = max(0, east_idx - west_idx + 1) * max(0, north_idx - south_idx + 1)
        if count <= max_tiles or tile_deg >= 45.0:
            break
        tile_deg = _nice_tile_deg(tile_deg * 1.5)

    tiles: list[FieldTile] = []
    for row, lat_idx in enumerate(range(south_idx, north_idx + 1)):
        for col, lon_idx in enumerate(range(west_idx, east_idx + 1)):
            west = lon_idx * tile_deg
            east = west + tile_deg
            south = lat_idx * tile_deg
            north = south + tile_deg
            clipped = BBox(
                west=max(safe.west, west),
                south=max(safe.south, south),
                east=min(safe.east, east),
                north=min(safe.north, north),
            )
            tile_id = f"deg{tile_deg:g}:{lon_idx}:{lat_idx}"
            tiles.append(FieldTile(id=tile_id, bbox=clipped, row=row, col=col, tile_deg=tile_deg))

    meta = {
        "planner": "stable_world_lattice_8x8_cap64",
        "requested_bbox": bbox.model_dump(mode="json"),
        "safe_bbox": safe.model_dump(mode="json"),
        "tile_deg": tile_deg,
        "max_axis_tiles": max_axis_tiles,
        "max_tiles": max_tiles,
        "tile_count": len(tiles),
        "tile_ids": [tile.id for tile in tiles],
        "parallelism": min(max_tiles, len(tiles)),
        "stable_across_zoom": True,
    }
    return tiles, meta


def run_tiles_parallel(tiles: Iterable[FieldTile], worker: Callable[[FieldTile], T], max_workers: int = 16) -> list[tuple[FieldTile, T]]:
    tiles_list = list(tiles)
    if not tiles_list:
        return []
    workers = max(1, min(max_workers, len(tiles_list)))
    out: list[tuple[FieldTile, T]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lftr-field-tile") as pool:
        futures = {pool.submit(worker, tile): tile for tile in tiles_list}
        for future in as_completed(futures):
            tile = futures[future]
            out.append((tile, future.result()))
    out.sort(key=lambda item: (item[0].row, item[0].col))
    return out
