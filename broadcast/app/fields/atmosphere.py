from __future__ import annotations

from datetime import datetime, timezone
import math

from app.fields.base import AtmosphereFieldFrame
from app.fields.scalar import ScalarField2D, clamp
from app.fields.tiles import stable_tile_plan, run_tiles_parallel
from app.schemas.scene import BBox

ATMOSPHERE_CHANNELS = [
    "cloud_density",
    "cloud_total",
    "low_cloud",
    "mid_cloud",
    "high_cloud",
    "rain_rate",
    "wind_u",
    "wind_v",
    "humidity",
    "temperature",
    "pressure",
]


def _gaussian(x: float, y: float, cx: float, cy: float, sx: float, sy: float, amp: float) -> float:
    return amp * math.exp(-(((x - cx) ** 2) / max(1e-6, 2 * sx * sx) + ((y - cy) ** 2) / max(1e-6, 2 * sy * sy)))


def _wrap_lon_delta(lon: float, center: float) -> float:
    return ((lon - center + 180.0) % 360.0) - 180.0


def _geo_gaussian(lon: float, lat: float, cx: float, cy: float, sx_deg: float, sy_deg: float, amp: float) -> float:
    dx = _wrap_lon_delta(lon, cx)
    dy = lat - cy
    return amp * math.exp(-((dx * dx) / max(1e-6, 2 * sx_deg * sx_deg) + (dy * dy) / max(1e-6, 2 * sy_deg * sy_deg)))


def _cell_atmosphere_values(lon: float, lat: float) -> dict[str, float]:
    """Stable synthetic atmosphere truth at an absolute lon/lat.

    This is still mock/fallback data when GFS is disabled, but the values are world-space
    instead of viewport-normalized.  A cloud at lon/lat therefore stays a cloud when the
    user zooms or pans and the backend retessellates the viewport.
    """
    x = ((lon + 180.0) % 360.0) / 360.0
    y = (lat + 90.0) / 180.0
    wave = 0.10 * math.sin((lon * 0.16 + lat * 0.21) * math.pi) + 0.08 * math.cos((lon * 0.05 - lat * 0.27) * math.pi)

    # SoCal/coastal anchored fallback features, plus broad absolute waves elsewhere.
    marine = (
        _geo_gaussian(lon, lat, -119.6, 33.8, 3.2, 1.25, 0.74)
        + _geo_gaussian(lon, lat, -118.0, 34.6, 2.7, 0.85, 0.42)
        + max(0.0, 0.28 * math.sin((lon + 124.0) * 0.34) * math.cos((lat - 31.0) * 0.38))
    )
    puff_field = (
        _geo_gaussian(lon, lat, -123.0, 36.2, 1.2, 0.75, 0.80)
        + _geo_gaussian(lon, lat, -118.6, 35.8, 1.35, 0.90, 0.65)
        + max(0.0, 0.22 * math.sin((x * 21.0 + y * 13.0) * math.pi))
    )
    storm_field = _geo_gaussian(lon, lat, -117.7, 33.45, 1.05, 0.90, 0.95) + max(0.0, 0.10 * math.cos((lon - lat) * 0.23))
    wisp_field = _geo_gaussian(lon, lat, -121.4, 37.4, 5.8, 0.42, 0.50) + max(0.0, 0.16 * math.cos((lon * 0.11 + lat * 0.19) * math.pi))

    low = clamp(0.08 + marine * 0.86 + wave * 0.20)
    mid = clamp(0.06 + puff_field * 0.70 + storm_field * 0.38 + wave * 0.24)
    high = clamp(0.05 + wisp_field * 0.82 + storm_field * 0.34 + max(0.0, wave) * 0.18)
    rain = clamp(storm_field * 0.76 + max(0.0, puff_field - 0.55) * 0.20 - 0.04)
    density = clamp(0.05 + low * 0.50 + mid * 0.42 + high * 0.28 + rain * 0.26 + wave * 0.22)
    total = clamp(max(density, low, mid * 0.92, high * 0.85))
    humidity = clamp(0.38 + low * 0.34 + mid * 0.18 + rain * 0.18 + 0.08 * math.sin(math.radians(lat * 3.0)))
    u = 0.22 + 0.34 * math.cos((lat + 6.0) * math.pi / 18.0) + 0.12 * math.sin(lon * math.pi / 17.0)
    v = 0.10 + 0.28 * math.sin((lon + 3.0) * math.pi / 22.0) - 0.08 * math.cos(lat * math.pi / 11.0)
    temp = 18.0 + (34.0 - lat) * 0.35 - density * 2.4 + (lon + 120.0) * 0.08
    pressure = 1012.0 - storm_field * 8.0 + high * 1.5 + (lat - 34.0) * 0.18
    return {
        "cloud_density": round(density, 3),
        "cloud_total": round(total, 3),
        "low_cloud": round(low, 3),
        "mid_cloud": round(mid, 3),
        "high_cloud": round(high, 3),
        "rain_rate": round(rain, 3),
        "wind_u": round(u, 3),
        "wind_v": round(v, 3),
        "humidity": round(humidity, 3),
        "temperature": round(temp, 3),
        "pressure": round(pressure, 3),
    }


def build_mock_atmosphere_frame(bbox: BBox, grid_shape: tuple[int, int] = (64, 64)) -> AtmosphereFieldFrame:
    """Build a dense fallback atmosphere scalar field from stable world-space values."""
    rows, cols = grid_shape
    channels = {name: [] for name in ATMOSPHERE_CHANNELS}
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = bbox.south + (bbox.north - bbox.south) * y
        row_values = {name: [] for name in ATMOSPHERE_CHANNELS}
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = bbox.west + (bbox.east - bbox.west) * x
            values = _cell_atmosphere_values(lon, lat)
            for name in ATMOSPHERE_CHANNELS:
                row_values[name].append(values[name])
        for name in ATMOSPHERE_CHANNELS:
            channels[name].append(row_values[name])

    return AtmosphereFieldFrame(
        bbox=bbox,
        valid_time=datetime.now(timezone.utc).isoformat(),
        grid_shape=grid_shape,
        levels=["low", "mid", "high"],
        channels=channels,
        metadata={
            "source": "mock_atmosphere_field_engine_pass1",
            "degraded": False,
            "field_engine": "xyz_scalar_field_pass1",
            "grid_shape": list(grid_shape),
            "z_axis": {"kind": "altitude_m", "levels_m": [900, 4200, 9800]},
            "interpolation_ready": "bilinear_2d_trilinear_3d_primitives",
            "cloud_feature_ready": True,
            "coordinate_model": "stable_world_space_lon_lat_not_viewport_normalized",
        },
    )


def build_tiled_mock_atmosphere_frame(
    bbox: BBox,
    grid_shape: tuple[int, int] = (64, 64),
    tile_grid_shape: tuple[int, int] = (18, 18),
    max_tiles: int = 64,
    max_workers: int = 16,
) -> AtmosphereFieldFrame:
    """Build a stitched atmosphere field from stable world tiles.

    External callers still receive one viewport-sized patch.  Internally we build/could
    fetch stable world-lattice tiles in parallel, then stitch/sample them into the final
    viewport grid.  This is the contract we will use for live GFS NCSS tile fetching.
    """
    tiles, tile_meta = stable_tile_plan(bbox, max_axis_tiles=8, max_tiles=max_tiles)

    def build_tile(tile):
        return build_mock_atmosphere_frame(tile.bbox, grid_shape=tile_grid_shape)

    tile_frames = run_tiles_parallel(tiles, build_tile, max_workers=max_workers)
    samplers: list[tuple[BBox, dict[str, ScalarField2D], str]] = []
    for tile, frame in tile_frames:
        samplers.append((tile.bbox, {name: ScalarField2D(name, frame.channels[name], tile.bbox.west, tile.bbox.south, tile.bbox.east, tile.bbox.north) for name in ATMOSPHERE_CHANNELS}, tile.id))

    rows, cols = grid_shape
    channels = {name: [] for name in ATMOSPHERE_CHANNELS}
    for row in range(rows):
        y = 0.0 if rows <= 1 else row / (rows - 1)
        lat = bbox.south + (bbox.north - bbox.south) * y
        row_values = {name: [] for name in ATMOSPHERE_CHANNELS}
        for col in range(cols):
            x = 0.0 if cols <= 1 else col / (cols - 1)
            lon = bbox.west + (bbox.east - bbox.west) * x
            matched = None
            for tile_bbox, tile_samplers, _tile_id in samplers:
                if tile_bbox.west - 1e-9 <= lon <= tile_bbox.east + 1e-9 and tile_bbox.south - 1e-9 <= lat <= tile_bbox.north + 1e-9:
                    matched = tile_samplers
                    break
            if matched is None:
                values = _cell_atmosphere_values(lon, lat)
                for name in ATMOSPHERE_CHANNELS:
                    row_values[name].append(values[name])
            else:
                for name in ATMOSPHERE_CHANNELS:
                    row_values[name].append(round(matched[name].bilinear(lon, lat), 3))
        for name in ATMOSPHERE_CHANNELS:
            channels[name].append(row_values[name])

    frame = AtmosphereFieldFrame(
        bbox=bbox,
        valid_time=datetime.now(timezone.utc).isoformat(),
        grid_shape=grid_shape,
        levels=["low", "mid", "high"],
        channels=channels,
        metadata={
            "source": "mock_atmosphere_tiled_field_engine_pass2",
            "degraded": False,
            "field_engine": "xyz_scalar_field_pass2_stable_tiled",
            "grid_shape": list(grid_shape),
            "z_axis": {"kind": "altitude_m", "levels_m": [900, 4200, 9800]},
            "cloud_feature_ready": True,
            "coordinate_model": "stable_world_space_lon_lat_not_viewport_normalized",
            "tile_plan": tile_meta,
            "tile_stitcher": "parallel_tile_build_then_bilinear_sample_to_viewport_grid",
            "future_live_fetch_contract": "replace tile worker with NCSS/RTOFS tile fetch while preserving stitched field contract",
        },
    )
    return frame
