from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Sequence

from app.fields.base import OceanFieldFrame
from app.fields.scalar import ScalarField2D, ScalarField3D, clamp, labels_from_depths, parse_depth_levels_m
from app.fields.tiles import stable_tile_plan, run_tiles_parallel
from app.schemas.scene import BBox
from app.services.marine_land_mask import marine_mask_for_bbox, marine_mask_for_point, marine_point_filter_summary

OCEAN_CHANNELS = [
    "sst_c",
    "water_temp_c",
    "current_u",
    "current_v",
    "bait_score",
    "salinity",
    "depth_m",
    "bathymetry_m",
    "bait_depth_m",
    "current_speed",
    "current_direction",
]

VOLUME_CHANNELS = ["water_temp_c", "current_u", "current_v", "salinity", "bait_score"]


def _gaussian(x: float, y: float, cx: float, cy: float, sx: float, sy: float, amp: float) -> float:
    return amp * math.exp(-(((x - cx) ** 2) / max(1e-6, 2 * sx * sx) + ((y - cy) ** 2) / max(1e-6, 2 * sy * sy)))


def _stable_xy(lon: float, lat: float) -> tuple[float, float]:
    # World-space normalized coordinates.  Mock ocean features no longer depend on
    # the current viewport bbox, so currents/bait remain coherent through zoom/pan.
    return (((lon + 180.0) % 360.0) / 360.0, (lat + 90.0) / 180.0)


def _wrap_lon_delta(lon: float, center: float) -> float:
    return ((lon - center + 180.0) % 360.0) - 180.0


def _geo_gaussian(lon: float, lat: float, cx: float, cy: float, sx_deg: float, sy_deg: float, amp: float) -> float:
    dx = _wrap_lon_delta(lon, cx)
    dy = lat - cy
    return amp * math.exp(-((dx * dx) / max(1e-6, 2 * sx_deg * sx_deg) + (dy * dy) / max(1e-6, 2 * sy_deg * sy_deg)))


def _cell_ocean_values(lon: float, lat: float, depth_m: float) -> dict[str, float]:
    """Synthetic ocean truth function for pass-2 scalar engine.

    Values are anchored to absolute lon/lat, not viewport-normalized coordinates.  This
    keeps current/bait/ocean structures stable when zoom or pan changes the requested
    bbox, and matches the future live RTOFS tile-cache contract.
    """
    x, y = _stable_xy(lon, lat)
    front = 0.5 + 0.5 * math.sin((lon * 0.19 - lat * 0.14) * math.pi)
    eddy_a = _geo_gaussian(lon, lat, -121.7, 34.4, 1.7, 1.1, 1.0) + _gaussian(x, y, 0.28, 0.44, 0.16, 0.13, 0.35)
    eddy_b = _geo_gaussian(lon, lat, -118.9, 33.7, 1.4, 1.0, 0.85) + _gaussian(x, y, 0.72, 0.58, 0.18, 0.16, 0.28)
    coastal_cool = _geo_gaussian(lon, lat, -117.9, 34.0, 2.6, 1.6, 1.0) + _gaussian(x, y, 0.82, 0.32, 0.36, 0.22, 0.22)
    z_decay = math.exp(-depth_m / 85.0)
    thermocline = 1.0 / (1.0 + math.exp(-(depth_m - 32.0) / 9.0))

    temp = 20.5 + 2.1 * front + 1.1 * eddy_a - 0.9 * coastal_cool - 0.028 * depth_m - 1.8 * thermocline
    u = (-0.34 + 0.74 * x + 0.22 * math.sin(y * math.pi * 2.0) + 0.18 * eddy_a - 0.16 * eddy_b) * (0.38 + 0.62 * z_decay)
    v = (0.10 + 0.46 * y - 0.18 * math.cos(x * math.pi * 2.0) + 0.16 * eddy_b) * (0.42 + 0.58 * z_decay)
    salinity = 33.7 + 0.62 * x + 0.18 * y + 0.006 * depth_m - 0.28 * eddy_a
    chlorophyll_proxy = clamp(0.12 + 0.58 * eddy_a + 0.34 * eddy_b + 0.22 * coastal_cool - abs(depth_m - 22.0) / 95.0)
    speed = math.hypot(u, v)
    temp_fit = clamp(1.0 - abs(temp - 19.2) / 6.0)
    speed_fit = clamp(1.0 - abs(speed - 0.38) / 0.82)
    depth_fit = clamp(1.0 - abs(depth_m - 22.0) / 70.0)
    bait = clamp(0.08 + temp_fit * 0.28 + speed_fit * 0.26 + depth_fit * 0.22 + chlorophyll_proxy * 0.30)
    return {
        "water_temp_c": round(temp, 3),
        "current_u": round(u, 3),
        "current_v": round(v, 3),
        "salinity": round(salinity, 3),
        "bait_score": round(bait, 3),
    }


def _bathymetry_grid(bbox: BBox, grid_shape: tuple[int, int]) -> list[list[float]]:
    rows, cols = grid_shape
    out: list[list[float]] = []
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = bbox.south + (bbox.north - bbox.south) * y
        row_out: list[float] = []
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = bbox.west + (bbox.east - bbox.west) * x
            xx, yy = _stable_xy(lon, lat)
            shelf = 26 + 520 * clamp((0.72 - xx) / 0.72) ** 1.7
            canyon = 420 * _geo_gaussian(lon, lat, -121.0, 34.2, 1.3, 1.6, 1.0) + 120 * _gaussian(xx, yy, 0.42, 0.42, 0.14, 0.18, 1.0)
            row_out.append(round(max(8.0, shelf + canyon + (lat - 32.0) * 6.0), 3))
        out.append(row_out)
    return out


def build_mock_ocean_volume(bbox: BBox, grid_shape: tuple[int, int] = (64, 64), depth_levels: Sequence[str] | str | None = None) -> dict[str, ScalarField3D]:
    z_levels = parse_depth_levels_m(depth_levels)
    rows, cols = grid_shape
    volumes: dict[str, list[list[list[float]]]] = {name: [] for name in VOLUME_CHANNELS}
    for z in z_levels:
        layer_values = {name: [] for name in VOLUME_CHANNELS}
        for row in range(rows):
            y = 0.0 if rows <= 1 else row / (rows - 1)
            rows_for_channel = {name: [] for name in VOLUME_CHANNELS}
            for col in range(cols):
                x = 0.0 if cols <= 1 else col / (cols - 1)
                lon = bbox.west + (bbox.east - bbox.west) * x
                lat = bbox.south + (bbox.north - bbox.south) * y
                values = _cell_ocean_values(lon, lat, z)
                for name in VOLUME_CHANNELS:
                    rows_for_channel[name].append(values[name])
            for name in VOLUME_CHANNELS:
                layer_values[name].append(rows_for_channel[name])
        for name in VOLUME_CHANNELS:
            volumes[name].append(layer_values[name])
    return {
        name: ScalarField3D(name=name, values=values, west=bbox.west, south=bbox.south, east=bbox.east, north=bbox.north, z_levels=z_levels, z_kind="depth_m_positive_down")
        for name, values in volumes.items()
    }


def _sample_volume_grid(field: ScalarField3D, depth_m: float, grid_shape: tuple[int, int]) -> list[list[float]]:
    rows, cols = grid_shape
    out: list[list[float]] = []
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = field.south + (field.north - field.south) * y
        row_out: list[float] = []
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = field.west + (field.east - field.west) * x
            row_out.append(round(field.trilinear(lon, lat, depth_m), 3))
        out.append(row_out)
    return out


def _max_bait_column(volume: ScalarField3D, grid_shape: tuple[int, int], max_depth_m: float = 50.0) -> tuple[list[list[float]], list[list[float]]]:
    rows, cols = grid_shape
    candidate_depths = [z for z in volume.z_levels if z <= max_depth_m] or [volume.z_levels[0]]
    score_grid: list[list[float]] = []
    depth_grid: list[list[float]] = []
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = volume.south + (volume.north - volume.south) * y
        score_row: list[float] = []
        depth_row: list[float] = []
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = volume.west + (volume.east - volume.west) * x
            samples = [(volume.trilinear(lon, lat, z), z) for z in candidate_depths]
            best_score, best_depth = max(samples, key=lambda item: item[0])
            score_row.append(round(best_score, 3))
            depth_row.append(round(best_depth, 3))
        score_grid.append(score_row)
        depth_grid.append(depth_row)
    return score_grid, depth_grid


def build_mock_ocean_frame(bbox: BBox, grid_shape: tuple[int, int] = (64, 64), depth_levels: Sequence[str] | str | None = None) -> OceanFieldFrame:
    volumes = build_mock_ocean_volume(bbox, grid_shape=grid_shape, depth_levels=depth_levels)
    z_levels = volumes["water_temp_c"].z_levels
    temp_surface = _sample_volume_grid(volumes["water_temp_c"], 0.0, grid_shape)
    current_u = _sample_volume_grid(volumes["current_u"], 0.0, grid_shape)
    current_v = _sample_volume_grid(volumes["current_v"], 0.0, grid_shape)
    salinity = _sample_volume_grid(volumes["salinity"], 0.0, grid_shape)
    bait_score, bait_depth = _max_bait_column(volumes["bait_score"], grid_shape, max_depth_m=50.0)
    channels: dict[str, list[list[float]]] = {
        "sst_c": temp_surface,
        "water_temp_c": temp_surface,
        "current_u": current_u,
        "current_v": current_v,
        "salinity": salinity,
        "depth_m": [[0.0 for _ in range(grid_shape[1])] for _ in range(grid_shape[0])],
        "bathymetry_m": _bathymetry_grid(bbox, grid_shape),
        "bait_score": bait_score,
        "bait_depth_m": bait_depth,
    }
    frame = OceanFieldFrame(
        bbox=bbox,
        valid_time=datetime.now(timezone.utc).isoformat(),
        grid_shape=grid_shape,
        depth_levels=labels_from_depths(z_levels),
        channels=channels,
        metadata={
            "source": "mock_ocean_xyz_scalar_field_pass2",
            "degraded": False,
            "field_engine": "xyz_scalar_field_pass2_stable_tiled",
            "grid_shape": list(grid_shape),
            "z_axis": {"kind": "depth_m_positive_down", "levels_m": z_levels},
            "volume_channels": VOLUME_CHANNELS,
            "stream_contract": "surface channels plus derived column bait_score; backend can sample x/y/depth with trilinear interpolation",
            "coordinate_model": "stable_world_space_lon_lat_not_viewport_normalized",
            "ocean_compute_ready": True,
        },
    )
    enrich_ocean_diagnostics(frame)
    return apply_marine_point_mask(frame, purpose="mock_ocean_frame")


def build_tiled_mock_ocean_frame(
    bbox: BBox,
    grid_shape: tuple[int, int] = (64, 64),
    depth_levels: Sequence[str] | str | None = None,
    tile_grid_shape: tuple[int, int] = (18, 18),
    max_tiles: int = 64,
    max_workers: int = 16,
) -> OceanFieldFrame:
    """Build a stitched ocean field from stable world tiles.

    This mirrors the cloud/atmosphere tile contract and keeps ocean/current/bait values
    coherent across zoom levels.  Future live RTOFS workers replace the mock tile worker
    without changing the stitched stream patch contract.
    """
    tiles, tile_meta = stable_tile_plan(bbox, max_axis_tiles=8, max_tiles=max_tiles)

    def build_tile(tile):
        return build_mock_ocean_frame(tile.bbox, grid_shape=tile_grid_shape, depth_levels=depth_levels)

    tile_frames = run_tiles_parallel(tiles, build_tile, max_workers=max_workers)
    surface_channels = [name for name in OCEAN_CHANNELS if name in (tile_frames[0][1].channels if tile_frames else {})]
    samplers: list[tuple[BBox, dict[str, ScalarField2D], str]] = []
    for tile, frame in tile_frames:
        samplers.append((tile.bbox, {name: ScalarField2D(name, frame.channels[name], tile.bbox.west, tile.bbox.south, tile.bbox.east, tile.bbox.north) for name in surface_channels}, tile.id))

    rows, cols = grid_shape
    channels: dict[str, list[list[float]]] = {name: [] for name in surface_channels}
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = bbox.south + (bbox.north - bbox.south) * y
        row_values = {name: [] for name in surface_channels}
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = bbox.west + (bbox.east - bbox.west) * x
            matched = None
            for tile_bbox, tile_samplers, _tile_id in samplers:
                if tile_bbox.west - 1e-9 <= lon <= tile_bbox.east + 1e-9 and tile_bbox.south - 1e-9 <= lat <= tile_bbox.north + 1e-9:
                    matched = tile_samplers
                    break
            if matched is None:
                values = _cell_ocean_values(lon, lat, 0.0)
                for name in surface_channels:
                    row_values[name].append(round(values.get(name, 0.0), 3))
            else:
                for name in surface_channels:
                    row_values[name].append(round(matched[name].bilinear(lon, lat), 3))
        for name in surface_channels:
            channels[name].append(row_values[name])

    # Ensure derived diagnostics are present even if the tile list was empty.
    z_levels = parse_depth_levels_m(depth_levels)
    frame = OceanFieldFrame(
        bbox=bbox,
        valid_time=datetime.now(timezone.utc).isoformat(),
        grid_shape=grid_shape,
        depth_levels=labels_from_depths(z_levels),
        channels=channels,
        metadata={
            "source": "mock_ocean_tiled_xyz_scalar_field_pass2",
            "degraded": False,
            "field_engine": "xyz_scalar_field_pass2_stable_tiled",
            "grid_shape": list(grid_shape),
            "z_axis": {"kind": "depth_m_positive_down", "levels_m": z_levels},
            "volume_channels": VOLUME_CHANNELS,
            "coordinate_model": "stable_world_space_lon_lat_not_viewport_normalized",
            "tile_plan": tile_meta,
            "tile_stitcher": "parallel_tile_build_then_bilinear_sample_to_viewport_grid",
            "future_live_fetch_contract": "replace tile worker with parallel bounded RTOFS/NCSS tile fetch while preserving stitched stream patch contract",
        },
    )
    enrich_ocean_diagnostics(frame)
    if "bait_score" not in frame.channels:
        frame.channels["bait_score"] = derive_bait_score(frame.channels)
    return apply_marine_point_mask(frame, purpose="tiled_mock_ocean_frame")



def _cell_lon_lat_for_bbox(bbox: BBox, row: int, col: int, grid_shape: tuple[int, int]) -> tuple[float, float]:
    rows, cols = grid_shape
    x = 0.0 if cols <= 1 else col / (cols - 1)
    y = 0.0 if rows <= 1 else row / (rows - 1)
    return (bbox.west + (bbox.east - bbox.west) * x, bbox.south + (bbox.north - bbox.south) * y)


def apply_marine_point_mask(frame: OceanFieldFrame, *, purpose: str = "ocean_frame") -> OceanFieldFrame:
    """Zero ocean-derived channels at conservative land-core points.

    This protects all downstream consumers: raw ocean patches, bait clusters,
    boats, and shark-intel scoring.  It is intentionally point-level so a mixed
    coastal bbox can still use marine data without letting land cells render.
    """
    rows, cols = frame.grid_shape
    if rows <= 0 or cols <= 0 or not frame.channels:
        frame.metadata.setdefault("marine_point_mask", marine_point_filter_summary(0, 0, purpose))
        return frame
    checked = rows * cols
    kept = 0
    zero_channels = {"sst_c", "water_temp_c", "current_u", "current_v", "bait_score", "salinity", "depth_m", "bathymetry_m", "bait_depth_m", "current_speed", "current_direction"}
    for row in range(rows):
        for col in range(cols):
            lon, lat = _cell_lon_lat_for_bbox(frame.bbox, row, col, frame.grid_shape)
            if marine_mask_for_point(lon, lat).get("should_render_ocean", True):
                kept += 1
                continue
            for name, grid in frame.channels.items():
                if name in zero_channels and row < len(grid) and col < len(grid[row]):
                    grid[row][col] = 0.0
    frame.metadata["marine_point_mask"] = marine_point_filter_summary(checked, kept, purpose)
    return frame


def stitch_ocean_tile_frames(
    bbox: BBox,
    tile_frames: list[tuple[BBox, OceanFieldFrame, str]],
    *,
    grid_shape: tuple[int, int] = (64, 64),
    depth_levels: Sequence[str] | str | None = None,
    source: str = "rtofs_ncep_tiled_stitched",
    tile_plan: dict | None = None,
) -> OceanFieldFrame:
    """Stitch already-fetched live/last-good RTOFS tiles into one viewport frame."""
    if not tile_frames:
        frame = OceanFieldFrame(
            bbox=bbox,
            valid_time=datetime.now(timezone.utc).isoformat(),
            grid_shape=(0, 0),
            depth_levels=labels_from_depths(parse_depth_levels_m(depth_levels)),
            channels={},
            metadata={
                "source": f"no_data:{source}",
                "field_engine": "tiled_ocean_provider_no_tiles",
                "tile_plan": tile_plan or {},
                "marine_land_mask": marine_mask_for_bbox(bbox),
                "data_state": "no_data",
            },
        )
        return frame

    surface_channels = sorted({name for _, frame, _ in tile_frames for name in frame.channels.keys()})
    samplers: list[tuple[BBox, dict[str, ScalarField2D], str]] = []
    for tile_bbox, frame, tile_id in tile_frames:
        if frame.grid_shape[0] <= 0 or frame.grid_shape[1] <= 0:
            continue
        samplers.append((tile_bbox, {name: ScalarField2D(name, frame.channels[name], tile_bbox.west, tile_bbox.south, tile_bbox.east, tile_bbox.north) for name in surface_channels if name in frame.channels}, tile_id))

    rows, cols = grid_shape
    channels: dict[str, list[list[float]]] = {name: [] for name in surface_channels}
    for row in range(rows):
        lon_lat = [_cell_lon_lat_for_bbox(bbox, row, col, grid_shape) for col in range(cols)]
        row_values = {name: [] for name in surface_channels}
        for lon, lat in lon_lat:
            matched = None
            for tile_bbox, tile_samplers, _tile_id in samplers:
                if tile_bbox.west - 1e-9 <= lon <= tile_bbox.east + 1e-9 and tile_bbox.south - 1e-9 <= lat <= tile_bbox.north + 1e-9:
                    matched = tile_samplers
                    break
            for name in surface_channels:
                if matched and name in matched:
                    row_values[name].append(round(matched[name].bilinear(lon, lat), 3))
                else:
                    row_values[name].append(0.0)
        for name in surface_channels:
            channels[name].append(row_values[name])

    z_levels = parse_depth_levels_m(depth_levels)
    frame = OceanFieldFrame(
        bbox=bbox,
        valid_time=datetime.now(timezone.utc).isoformat(),
        grid_shape=grid_shape,
        depth_levels=labels_from_depths(z_levels),
        channels=channels,
        metadata={
            "source": source,
            "degraded": False,
            "field_engine": "tiled_rtofs_ocean_stitcher",
            "grid_shape": list(grid_shape),
            "z_axis": {"kind": "depth_m_positive_down", "levels_m": z_levels},
            "tile_plan": tile_plan or {},
            "tile_stitcher": "parallel_rtofs_tile_fetch_then_bilinear_sample_to_viewport_grid",
            "marine_land_mask": marine_mask_for_bbox(bbox),
            "data_state": "live_or_last_good_tiles",
        },
    )
    if "current_u" in frame.channels and "current_v" in frame.channels:
        enrich_ocean_diagnostics(frame)
    if "bait_score" not in frame.channels and {"sst_c", "current_u", "current_v"}.issubset(frame.channels.keys()):
        frame.channels["bait_score"] = derive_bait_score(frame.channels)
    return apply_marine_point_mask(frame, purpose="stitched_rtofs_ocean_frame")

def sample_mock_ocean(bbox: BBox, lon: float, lat: float, depth_m: float = 0.0, grid_shape: tuple[int, int] = (64, 64), depth_levels: Sequence[str] | str | None = None) -> dict[str, float]:
    volumes = build_mock_ocean_volume(bbox, grid_shape=grid_shape, depth_levels=depth_levels)
    return {name: round(field.trilinear(lon, lat, depth_m), 3) for name, field in volumes.items()}


def derive_bait_score(channels: dict[str, list[list[float]]]) -> list[list[float]]:
    if "bait_score" in channels:
        return channels["bait_score"]
    sst = channels["sst_c"]
    u = channels["current_u"]
    v = channels["current_v"]
    rows, cols = len(sst), len(sst[0])
    score: list[list[float]] = []
    for row in range(rows):
        out_row: list[float] = []
        for col in range(cols):
            temp = sst[row][col]
            speed = math.hypot(u[row][col], v[row][col])
            temp_fit = clamp(1.0 - abs(temp - 19.2) / 6.0)
            speed_fit = clamp(1.0 - abs(speed - 0.38) / 0.82)
            out_row.append(round(clamp((temp_fit * 0.48) + (speed_fit * 0.38) + 0.14), 3))
        score.append(out_row)
    return score


def enrich_ocean_diagnostics(frame: OceanFieldFrame) -> None:
    u = frame.channels["current_u"]
    v = frame.channels["current_v"]
    rows, cols = len(u), len(u[0])
    frame.channels["current_speed"] = [[round(math.hypot(u[row][col], v[row][col]), 3) for col in range(cols)] for row in range(rows)]
    frame.channels["current_direction"] = [[round(math.degrees(math.atan2(v[row][col], u[row][col])), 3) for col in range(cols)] for row in range(rows)]
