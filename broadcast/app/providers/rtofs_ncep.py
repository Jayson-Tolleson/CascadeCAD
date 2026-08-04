from __future__ import annotations

import hashlib
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np
try:
    from netCDF4 import Dataset, num2date
except Exception:  # pragma: no cover - installer requirements install netCDF4 on target hosts.
    Dataset = None  # type: ignore[assignment]
    num2date = None  # type: ignore[assignment]

from app.core.config import get_settings
from app.fields.base import OceanFieldFrame
from app.fields.ocean import apply_marine_point_mask, derive_bait_score, enrich_ocean_diagnostics, stitch_ocean_tile_frames
from app.fields.scalar import labels_from_depths, parse_depth_levels_m
from app.fields.tiles import FieldTile, run_tiles_parallel, stable_tile_plan
from app.providers.provider_status import ProviderStatus, now_iso
from app.providers.rtofs_aliases import aliases_used
from app.providers.rtofs_cache import RTOFSCache
from app.schemas.scene import BBox
from app.services.marine_land_mask import marine_mask_for_bbox

RTOFS_PROVIDER_NAME = "rtofs_ncep"

# The zippy reference established the important contract: never ask RTOFS for a
# whole moving viewport when only part of it is ocean.  This provider keeps that
# policy, but fills in the previously missing bounded NetCDF tile parser.
FILTER_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_rtofs_glo_2ds.pl"
SURFACE_FILES = ("rtofs_glo_2ds_n000_diag.nc", "rtofs_glo_2ds_n000_prog.nc")


def parse_depth_levels(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_rtofs_url(base_url: str, bbox: BBox, depth_levels: list[str], max_points: int) -> str:
    query: dict[str, str] = {
        "bbox": f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}",
        "depth": ";".join(depth_levels),
        "max_points": str(max_points),
        "vars": ",".join(alias[0] for alias in aliases_used().values()),
    }
    return f"{base_url}?{urllib.parse.urlencode(query)}"


def cache_key(bbox: BBox, depth_levels: list[str]) -> str:
    depth = "_".join(depth_levels)
    return f"rtofs_ocean_{bbox.west:.2f}_{bbox.south:.2f}_{bbox.east:.2f}_{bbox.north:.2f}_{depth}"


def frame_to_cache_payload(frame: OceanFieldFrame, status: ProviderStatus) -> dict[str, Any]:
    return {"frame": frame.model_dump(mode="json"), "status": status.model_dump(mode="json")}


def frame_from_cache_payload(payload: dict[str, Any]) -> tuple[OceanFieldFrame, ProviderStatus]:
    return OceanFieldFrame(**payload["frame"]), ProviderStatus(**payload["status"])


def _norm_lon_180(lon: float) -> float:
    return ((float(lon) + 180.0) % 360.0) - 180.0


def _norm_lon_360(lon: float) -> float:
    return float(lon) % 360.0


def _bbox_for_nomads_360(bbox: BBox) -> tuple[float, float, float, float]:
    # NOMADS RTOFS global grids commonly expose longitude as 0..360.
    left = _norm_lon_360(bbox.west)
    right = _norm_lon_360(bbox.east)
    if right <= left:
        right += 360.0
    return left, right, bbox.south, bbox.north


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        pass
    return fallback


def _as_array(value: Any) -> np.ndarray:
    arr = np.asanyarray(value)
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, np.nan)
    return np.asarray(arr, dtype=float)


def _casefold(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _var_score(var: Any, aliases: list[str]) -> int:
    name = _casefold(getattr(var, "name", ""))
    fields = [name]
    for attr in ("standard_name", "long_name", "description", "GRIB_name"):
        try:
            value = getattr(var, attr)
        except Exception:
            value = None
        if value:
            fields.append(_casefold(str(value)))
    alias_keys = [_casefold(alias) for alias in aliases]
    score = 0
    for alias in alias_keys:
        for idx, field in enumerate(fields):
            if field == alias:
                score = max(score, 100 - idx)
            elif alias in field or field in alias:
                score = max(score, 70 - idx)
    return score


def _find_variable(ds: Any, aliases: list[str]) -> Any | None:
    best: tuple[int, str, Any] | None = None
    for name, var in ds.variables.items():
        if len(getattr(var, "dimensions", ())) < 2:
            continue
        score = _var_score(var, aliases + [name])
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, name, var)
    return best[2] if best else None


def _find_coord(ds: Any, wanted: str, preferred_dims: tuple[str, str] | None = None) -> np.ndarray | None:
    lat_aliases = ["lat", "latitude", "nav_lat", "Latitude", "y"]
    lon_aliases = ["lon", "longitude", "nav_lon", "Longitude", "x"]
    aliases = lat_aliases if wanted == "lat" else lon_aliases
    preferred = set(preferred_dims or ())
    best: tuple[int, str, Any] | None = None
    for name, var in ds.variables.items():
        lname = _casefold(name)
        dims = tuple(getattr(var, "dimensions", ()))
        attr_blob = " ".join(str(getattr(var, attr, "")) for attr in ("standard_name", "long_name", "units", "axis"))
        field = _casefold(f"{lname} {attr_blob}")
        score = 0
        for alias in aliases:
            a = _casefold(alias)
            if lname == a:
                score = max(score, 100)
            elif a in field:
                score = max(score, 70)
        if wanted == "lat" and "degrees_north" in field:
            score = max(score, 95)
        if wanted == "lon" and "degrees_east" in field:
            score = max(score, 95)
        if preferred and preferred.intersection(dims):
            score += 20
        if score and (best is None or score > best[0]):
            best = (score, name, var)
    if best:
        return _as_array(best[2][:])
    # Last resort: some datasets use dimension variables only.
    if preferred_dims:
        dim_name = preferred_dims[0 if wanted == "lat" else 1]
        if dim_name in ds.variables:
            return _as_array(ds.variables[dim_name][:])
    return None


def _surface_2d(var: Any) -> np.ndarray:
    arr = var[:]
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, np.nan)
    arr = np.asarray(arr, dtype=float)
    # Choose the first time/depth member until a 2-D horizontal plane remains.
    while arr.ndim > 2:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"variable {getattr(var, 'name', '<unnamed>')} did not reduce to a 2-D grid; shape={arr.shape}")
    fill_value = getattr(var, "_FillValue", None)
    if fill_value is not None:
        arr = np.where(arr == float(fill_value), np.nan, arr)
    missing = getattr(var, "missing_value", None)
    if missing is not None:
        try:
            arr = np.where(arr == float(missing), np.nan, arr)
        except Exception:
            pass
    return arr


def _nearest_1d_index(axis: np.ndarray, value: float) -> int:
    axis = np.asarray(axis, dtype=float).reshape(-1)
    if axis.size == 0:
        return 0
    return int(np.nanargmin(np.abs(axis - value)))


def _nearest_2d_index(lat_grid: np.ndarray, lon_grid: np.ndarray, lon: float, lat: float) -> tuple[int, int]:
    lon_grid = np.asarray(lon_grid, dtype=float)
    lat_grid = np.asarray(lat_grid, dtype=float)
    # Match the data longitude domain to avoid dateline/0..360 errors.
    finite_lon = lon_grid[np.isfinite(lon_grid)]
    target_lon = lon
    if finite_lon.size and np.nanmedian(finite_lon) > 180:
        target_lon = _norm_lon_360(lon)
        lon_grid_cmp = np.mod(lon_grid, 360.0)
    else:
        target_lon = _norm_lon_180(lon)
        lon_grid_cmp = ((lon_grid + 180.0) % 360.0) - 180.0
    dlon = np.abs(lon_grid_cmp - target_lon)
    dlon = np.minimum(dlon, 360.0 - dlon)
    dist = (lat_grid - lat) ** 2 + dlon ** 2
    if not np.isfinite(dist).any():
        return 0, 0
    idx = int(np.nanargmin(dist))
    return tuple(int(x) for x in np.unravel_index(idx, dist.shape))  # type: ignore[return-value]


def _grid_value(data: np.ndarray, lat_axis: np.ndarray, lon_axis: np.ndarray, lon: float, lat: float) -> float:
    if lat_axis.ndim == 1 and lon_axis.ndim == 1:
        finite_lon = lon_axis[np.isfinite(lon_axis)]
        target_lon = _norm_lon_360(lon) if finite_lon.size and np.nanmedian(finite_lon) > 180 else _norm_lon_180(lon)
        lon_cmp = np.mod(lon_axis, 360.0) if finite_lon.size and np.nanmedian(finite_lon) > 180 else ((lon_axis + 180.0) % 360.0) - 180.0
        row = _nearest_1d_index(lat_axis, lat)
        col = int(np.nanargmin(np.minimum(np.abs(lon_cmp - target_lon), 360.0 - np.abs(lon_cmp - target_lon)))) if lon_cmp.size else 0
    else:
        row, col = _nearest_2d_index(lat_axis, lon_axis, lon, lat)
    row = max(0, min(int(row), data.shape[0] - 1))
    col = max(0, min(int(col), data.shape[1] - 1))
    value = _safe_float(data[row, col], float("nan"))
    if math.isfinite(value):
        return value
    # Small local finite-neighbor fallback; avoids NaN pinholes in coastal tiles.
    r0, r1 = max(0, row - 2), min(data.shape[0], row + 3)
    c0, c1 = max(0, col - 2), min(data.shape[1], col + 3)
    neighborhood = data[r0:r1, c0:c1]
    finite = neighborhood[np.isfinite(neighborhood)]
    return _safe_float(float(np.nanmean(finite)), 0.0) if finite.size else 0.0


def _normalize_temperature(value: float, units: str) -> float:
    u = units.lower()
    if "kelvin" in u or u.strip() in {"k", "degk"}:
        return value - 273.15
    if "fahrenheit" in u or "degf" in u:
        return (value - 32.0) * 5.0 / 9.0
    # RTOFS/NetCDF usually stores C for surface SST after NOMADS filtering.
    if value > 120.0:
        return value - 273.15
    return value


def _normalize_current(value: float, units: str) -> float:
    u = units.lower()
    if "cm" in u and "/s" in u:
        return value / 100.0
    if "knot" in u or u in {"kt", "kts"}:
        return value * 0.514444
    return value


def _normalize_channel(name: str, value: float, units: str) -> float:
    if name in {"sst_c", "water_temp_c"}:
        return _normalize_temperature(value, units)
    if name in {"current_u", "current_v"}:
        return _normalize_current(value, units)
    return value


def _valid_time_from_dataset(ds: Any) -> str:
    for name in ("time", "MT", "valid_time", "forecast_time"):
        var = ds.variables.get(name)
        if var is None:
            continue
        units = getattr(var, "units", None)
        try:
            raw = var[:]
            first = np.ravel(raw)[0]
            if units:
                decoded = num2date(first, units=units, only_use_cftime_datetimes=False)
                if hasattr(decoded, "isoformat"):
                    return decoded.isoformat()
            return str(first)
        except Exception:
            continue
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _open_dataset(path: str) -> Iterator[Any]:
    if Dataset is None:
        raise RuntimeError("netCDF4 is not installed; run install.sh or pip install -r requirements.txt")
    ds = Dataset(path, "r")
    try:
        yield ds
    finally:
        ds.close()


class RTOFSNCEPProvider:
    name = RTOFS_PROVIDER_NAME

    def __init__(self) -> None:
        self.settings = get_settings()
        self.depth_levels = parse_depth_levels(self.settings.rtofs_depth_levels)
        self.cache = RTOFSCache(self.settings.rtofs_cache_dir)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            mode=self.settings.rtofs_provider_mode,
            enabled=self.settings.rtofs_enabled,
            generated_time=now_iso(),
            degraded=False,
            details={
                "base_url": self.settings.rtofs_nomads_base,
                "ttl_seconds": self.settings.rtofs_ttl_seconds,
                "max_grid_points": self.settings.rtofs_max_grid_points,
                "depth_levels": self.depth_levels,
                "field_engine_depth_levels_m": self.settings.field_engine_depth_levels_m,
                "sample_interface": "sample(lon, lat, depth_m, time)",
                "bounded_parser": "nomads_filter_or_local_netcdf_tile_parser",
                "zippy_contract": "tile-only ocean policy retained; live parser implemented in main app",
                "provider_tiling": {
                    "enabled": True,
                    "planner": "stable_world_lattice_tile_plan",
                    "max_tiles": self.settings.field_engine_max_tiles,
                    "max_workers": self.settings.field_engine_tile_workers,
                    "tile_grid_size": self.settings.field_engine_tile_grid_size,
                    "policy": "never request one huge RTOFS viewport; split bbox into land-mask-filtered parallel ocean tiles",
                },
            },
        )

    def fetch_ocean(self, bbox: BBox) -> tuple[OceanFieldFrame, ProviderStatus]:
        mask = marine_mask_for_bbox(bbox)
        tile_plan = self._ocean_tile_plan(bbox)
        if self.settings.marine_land_mask_enabled and not mask.get("should_query_ocean", True):
            return self._no_data_frame(
                bbox,
                reason="marine land mask skipped ocean provider for landlocked interior bbox",
                marine_mask=mask,
                tile_plan=tile_plan,
            )

        mode = self.settings.rtofs_provider_mode
        if mode == "mock":
            return self._no_data_frame(
                bbox,
                reason="RTOFS provider is in mock mode; live tile parser not used and synthetic fallback is not promoted",
                marine_mask=mask,
                tile_plan=tile_plan,
            )

        if not self.settings.rtofs_enabled:
            return self._no_data_frame(
                bbox,
                reason="RTOFS provider not enabled for live parsing; tiled request plan prepared but not executed",
                marine_mask=mask,
                tile_plan=tile_plan,
            )

        try:
            return self._live_tiled_frame(bbox, mask, tile_plan)
        except Exception as exc:
            cached = self._last_good(bbox, str(exc), tile_plan=tile_plan, marine_mask=mask)
            if cached:
                return cached
            return self._no_data_frame(
                bbox,
                reason=f"tiled live RTOFS failed and no stitched last-good cache exists: {exc}",
                marine_mask=mask,
                tile_plan=tile_plan,
            )

    def sample(self, lon: float, lat: float, depth_m: float = 0, time: str | None = None) -> dict[str, float | str | None]:
        pad = max(0.06, min(0.25, abs(depth_m) / 1000.0))
        bbox = BBox(west=lon - pad, south=lat - pad, east=lon + pad, north=lat + pad)
        frame, status = self.fetch_ocean(bbox)
        if frame.grid_shape[0] <= 0 or frame.grid_shape[1] <= 0:
            return {"lon": lon, "lat": lat, "depth_m": depth_m, "time": time, "status": "no_data", "error": status.error}
        rows, cols = frame.grid_shape
        row = max(0, min(rows - 1, int(round((lat - bbox.south) / max(1e-9, bbox.north - bbox.south) * (rows - 1)))))
        col = max(0, min(cols - 1, int(round((lon - bbox.west) / max(1e-9, bbox.east - bbox.west) * (cols - 1)))))
        out: dict[str, float | str | None] = {"lon": lon, "lat": lat, "depth_m": depth_m, "time": time, "status": "ok" if status.live_ok else "last_good_or_no_data"}
        for name, grid in frame.channels.items():
            try:
                out[name] = float(grid[row][col])
            except Exception:
                pass
        return out

    def _viewport_grid_shape(self) -> tuple[int, int]:
        size = max(8, int(self.settings.field_engine_grid_size))
        return (size, size)

    def _tile_grid_shape(self) -> tuple[int, int]:
        size = max(4, int(self.settings.field_engine_tile_grid_size))
        return (size, size)

    def _ocean_tile_plan(self, bbox: BBox) -> dict[str, Any]:
        tiles, meta = stable_tile_plan(
            bbox,
            max_axis_tiles=8,
            max_tiles=self.settings.field_engine_max_tiles,
            min_tile_deg=0.25,
        )
        tile_masks: list[dict[str, Any]] = []
        ocean_tiles: list[FieldTile] = []
        for tile in tiles:
            tile_mask = marine_mask_for_bbox(tile.bbox, pad_deg=0.0)
            kept = bool(tile_mask.get("should_query_ocean", True))
            if kept:
                ocean_tiles.append(tile)
            tile_masks.append({
                "tile_id": tile.id,
                "bbox": tile.bbox.model_dump(mode="json"),
                "should_query_ocean": kept,
                "classification": tile_mask.get("classification"),
                "reason": tile_mask.get("reason"),
                "matched_water": tile_mask.get("matched_water"),
                "land_core_hits": tile_mask.get("land_core_hits", []),
            })
        return {
            **meta,
            "provider": self.name,
            "rtofs_tiled": True,
            "all_ocean_requests_tiled": True,
            "no_whole_viewport_rtofs_call": True,
            "tile_masks": tile_masks,
            "ocean_tile_count": len(ocean_tiles),
            "skipped_land_tile_count": len(tiles) - len(ocean_tiles),
            "ocean_tile_ids": [tile.id for tile in ocean_tiles],
            "parallelism": min(self.settings.field_engine_tile_workers, max(1, len(ocean_tiles))),
            "request_url_examples": [self._candidate_urls(tile.bbox)[:2] for tile in ocean_tiles[:3]],
        }

    def _tiles_from_plan(self, bbox: BBox, tile_plan: dict[str, Any]) -> list[FieldTile]:
        tiles, _ = stable_tile_plan(
            bbox,
            max_axis_tiles=8,
            max_tiles=self.settings.field_engine_max_tiles,
            min_tile_deg=0.25,
        )
        keep = set(tile_plan.get("ocean_tile_ids", []))
        return [tile for tile in tiles if tile.id in keep]

    def _tile_max_points(self) -> int:
        return max(16, min(int(self.settings.rtofs_max_grid_points), self.settings.field_engine_tile_grid_size ** 2))

    def _live_tiled_frame(self, bbox: BBox, marine_mask: dict[str, Any], tile_plan: dict[str, Any]) -> tuple[OceanFieldFrame, ProviderStatus]:
        ocean_tiles = self._tiles_from_plan(bbox, tile_plan)
        if not ocean_tiles:
            return self._no_data_frame(bbox, "no ocean tiles remained after land-mask filtering", marine_mask=marine_mask, tile_plan=tile_plan)

        tile_errors: list[dict[str, str]] = []

        def worker(tile: FieldTile) -> tuple[BBox, OceanFieldFrame | None, str, str | None]:
            try:
                frame = self._live_tile_frame(tile)
                tile_status = self._status_from_frame(frame, live_ok=True, cache_hit=False, degraded=False, source=frame.metadata.get("source", "rtofs_live_tile"), marine_mask=marine_mask, tile_plan=tile_plan)
                self.cache.save(cache_key(tile.bbox, self.depth_levels), frame_to_cache_payload(frame, tile_status))
                return tile.bbox, frame, tile.id, None
            except Exception as exc:
                payload = self.cache.load(cache_key(tile.bbox, self.depth_levels))
                if payload:
                    frame, _status = frame_from_cache_payload(payload)
                    frame.metadata.update({"cache_status": "last_good_tile", "tile_error": str(exc), "tile_id": tile.id})
                    return tile.bbox, apply_marine_point_mask(frame, purpose="rtofs_last_good_tile"), tile.id, str(exc)
                return tile.bbox, None, tile.id, str(exc)

        results = run_tiles_parallel(ocean_tiles, worker, max_workers=self.settings.field_engine_tile_workers)
        good_tiles: list[tuple[BBox, OceanFieldFrame, str]] = []
        for _tile, result in results:
            tile_bbox, frame, tile_id, error = result
            if frame is not None:
                good_tiles.append((tile_bbox, frame, tile_id))
            if error:
                tile_errors.append({"tile_id": tile_id, "error": error})

        if not good_tiles:
            raise RuntimeError("all tiled RTOFS requests failed or had no last-good tile cache")

        frame = stitch_ocean_tile_frames(
            bbox,
            good_tiles,
            grid_shape=self._viewport_grid_shape(),
            depth_levels=self.settings.field_engine_depth_levels_m,
            source="rtofs_ncep_tiled_live_or_last_good",
            tile_plan={**tile_plan, "tile_errors": tile_errors[:16], "good_tile_count": len(good_tiles)},
        )
        frame.metadata.update({
            "provider": self.name,
            "marine_land_mask": marine_mask,
            "rtofs_tiled_contract": {**tile_plan, "tile_errors": tile_errors[:16], "good_tile_count": len(good_tiles)},
            "tile_errors": tile_errors[:16],
            "good_tile_count": len(good_tiles),
        })
        status = self._status_from_frame(
            frame,
            live_ok=True,
            cache_hit=bool(tile_errors),
            degraded=bool(tile_errors),
            source="rtofs_ncep_tiled_live_or_last_good",
            error="some RTOFS tiles used last-good cache or failed" if tile_errors else None,
            marine_mask=marine_mask,
            tile_plan={**tile_plan, "tile_errors": tile_errors[:16], "good_tile_count": len(good_tiles)},
        )
        self.cache.save(cache_key(bbox, self.depth_levels), frame_to_cache_payload(frame, status))
        return frame, status

    def _run_dates(self) -> list[str]:
        forced = os.environ.get("LFTR_RTOFS_RUN_DATE")
        if forced:
            return [forced]
        now = datetime.now(timezone.utc)
        return [(now - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(0, 4)]

    def _candidate_urls(self, bbox: BBox) -> list[str]:
        # Test/dev override: a local or file:// NetCDF path can stand in for NOMADS.
        override = os.environ.get("LFTR_RTOFS_LOCAL_NC") or os.environ.get("RTOFS_LOCAL_NC")
        if override:
            return [override]
        base = self.settings.rtofs_nomads_base.rstrip("/")
        left, right, bottom, top = _bbox_for_nomads_360(bbox)
        urls: list[str] = []
        for day in self._run_dates():
            dir_param = f"/rtofs.{day}"
            for filename in SURFACE_FILES:
                # Bounded NOMADS filter first.  all_var/all_lev keeps this robust
                # across NOAA variable-name changes while the tile bbox keeps it
                # small and respectful to the server.
                query = {
                    "dir": dir_param,
                    "file": filename,
                    "all_var": "on",
                    "all_lev": "on",
                    "subregion": "",
                    "leftlon": f"{left:.4f}",
                    "rightlon": f"{right:.4f}",
                    "bottomlat": f"{bottom:.4f}",
                    "toplat": f"{top:.4f}",
                }
                urls.append(f"{FILTER_BASE}?{urllib.parse.urlencode(query)}")
                # Direct file fallback; useful on systems where netCDF4/libcurl can
                # read remote datasets or where an HTTP cache/proxy is available.
                urls.append(f"{base}/rtofs.{day}/{filename}")
        return urls

    def _download_dataset(self, url: str, tile_id: str) -> str:
        if url.startswith("file://"):
            return urllib.parse.urlparse(url).path
        if Path(url).exists():
            return url
        cache_dir = Path(self.settings.rtofs_cache_dir) / "downloads"
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        target = cache_dir / f"{tile_id}_{digest}.nc"
        if target.exists() and time.time() - target.stat().st_mtime < max(30, self.settings.rtofs_ttl_seconds):
            return str(target)
        max_mb = float(os.environ.get("LFTR_RTOFS_DOWNLOAD_MAX_MB", "180"))
        max_bytes = int(max_mb * 1024 * 1024)
        req = urllib.request.Request(url, headers={"User-Agent": "LFTR-GFS-RTOFS/1.0 (+tile-only; contact: lftr.biz)"})
        with urllib.request.urlopen(req, timeout=float(self.settings.rtofs_timeout_seconds)) as response:
            content_type = response.headers.get("content-type", "")
            data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError(f"RTOFS response exceeded {max_mb:.0f}MB guardrail for {url}")
        if data[:1] == b"<" or "text/html" in content_type.lower() or b"No such file" in data[:512]:
            raise RuntimeError(f"RTOFS URL did not return NetCDF bytes: {url}; first_bytes={data[:160]!r}")
        tmp_fd, tmp_name = tempfile.mkstemp(prefix="rtofs_", suffix=".nc", dir=str(cache_dir))
        with os.fdopen(tmp_fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, target)
        return str(target)

    def _extract_channel_from_dataset(self, ds: Any, channel: str, bbox: BBox, grid_shape: tuple[int, int]) -> tuple[list[list[float]], dict[str, Any]] | None:
        var = _find_variable(ds, aliases_used().get(channel, [channel]))
        if var is None:
            return None
        data = _surface_2d(var)
        dims = tuple(getattr(var, "dimensions", ()))
        spatial_dims = dims[-2:] if len(dims) >= 2 else None
        lat_axis = _find_coord(ds, "lat", spatial_dims)
        lon_axis = _find_coord(ds, "lon", spatial_dims)
        if lat_axis is None or lon_axis is None:
            raise RuntimeError(f"could not identify latitude/longitude coordinates for variable {getattr(var, 'name', channel)}")
        # If coordinate arrays include time/depth dimensions too, squeeze them.
        while lat_axis.ndim > 2:
            lat_axis = lat_axis[0]
        while lon_axis.ndim > 2:
            lon_axis = lon_axis[0]
        units = str(getattr(var, "units", ""))
        rows, cols = grid_shape
        out: list[list[float]] = []
        finite_count = 0
        for row in range(rows):
            y = 0.0 if rows <= 1 else row / (rows - 1)
            lat = bbox.south + (bbox.north - bbox.south) * y
            out_row: list[float] = []
            for col in range(cols):
                x = 0.0 if cols <= 1 else col / (cols - 1)
                lon = bbox.west + (bbox.east - bbox.west) * x
                value = _grid_value(data, lat_axis, lon_axis, lon, lat)
                normed = round(_normalize_channel(channel, value, units), 3)
                if math.isfinite(normed):
                    finite_count += 1
                out_row.append(normed)
            out.append(out_row)
        return out, {"variable": getattr(var, "name", channel), "units": units, "finite_points": finite_count}

    def _live_tile_frame(self, tile: FieldTile) -> OceanFieldFrame:
        # This is the only place where real RTOFS NetCDF reading belongs.  The
        # whole-viewport call path is intentionally gone: live implementation opens
        # one small land-mask-approved stable tile and returns an OceanFieldFrame.
        bbox = tile.bbox
        grid_shape = self._tile_grid_shape()
        channels: dict[str, list[list[float]]] = {}
        variable_meta: dict[str, Any] = {}
        source_urls: list[str] = []
        errors: list[str] = []
        valid_time = datetime.now(timezone.utc).isoformat()

        for url in self._candidate_urls(bbox):
            if {"sst_c", "current_u", "current_v"}.issubset(channels):
                break
            try:
                path = self._download_dataset(url, tile.id)
                with _open_dataset(path) as ds:
                    valid_time = _valid_time_from_dataset(ds)
                    for channel in ("sst_c", "water_temp_c", "current_u", "current_v", "salinity"):
                        if channel in channels:
                            continue
                        result = self._extract_channel_from_dataset(ds, channel, bbox, grid_shape)
                        if result is None:
                            continue
                        grid, meta = result
                        channels[channel] = grid
                        variable_meta[channel] = {**meta, "url": url}
                    source_urls.append(url)
            except Exception as exc:
                errors.append(f"{url}: {exc}")
                continue

        if "water_temp_c" not in channels and "sst_c" in channels:
            channels["water_temp_c"] = channels["sst_c"]
        if "sst_c" not in channels and "water_temp_c" in channels:
            channels["sst_c"] = channels["water_temp_c"]
        missing = [name for name in ("sst_c", "current_u", "current_v") if name not in channels]
        if missing:
            raise RuntimeError(f"RTOFS tile parser missing required channel(s) {missing}; tried {len(errors)} URL(s); errors={errors[:4]}")

        rows, cols = grid_shape
        channels.setdefault("salinity", [[0.0 for _ in range(cols)] for _ in range(rows)])
        channels["depth_m"] = [[0.0 for _ in range(cols)] for _ in range(rows)]
        if "bait_score" not in channels:
            channels["bait_score"] = derive_bait_score(channels)
        # Surface RTOFS 2DS gives SST/currents but not the biomass depth itself.
        # Keep a scalar XYZ contract by publishing a best-column proxy depth that
        # downstream bait/intel panes can morph smoothly until the 3-D product is added.
        channels["bait_depth_m"] = [[round(12.0 + (1.0 - max(0.0, min(1.0, channels["bait_score"][r][c]))) * 34.0, 3) for c in range(cols)] for r in range(rows)]

        frame = OceanFieldFrame(
            bbox=bbox,
            valid_time=valid_time,
            grid_shape=grid_shape,
            depth_levels=labels_from_depths(parse_depth_levels_m(self.settings.field_engine_depth_levels_m)),
            channels=channels,
            metadata=self._metadata(
                bbox,
                "rtofs_ncep_bounded_netcdf_tile",
                live_ok=True,
                cache_status="live_tile",
                degraded=False,
                marine_mask=marine_mask_for_bbox(bbox),
                tile_plan={"tile_id": tile.id, "source_urls": source_urls, "errors": errors[:4]},
            ),
        )
        enrich_ocean_diagnostics(frame)
        frame.metadata.update({
            "tile_id": tile.id,
            "parser_status": "bounded_rtofs_tile_parser_ok",
            "source_urls": source_urls,
            "variable_meta": variable_meta,
            "download_error_count": len(errors),
            "errors_sample": errors[:4],
            "data_state": "live_tile",
            "z_axis": {"kind": "depth_m_positive_down", "levels_m": parse_depth_levels_m(self.settings.field_engine_depth_levels_m)},
            "bait_depth_source": "surface_rtofs_proxy_until_3d_product_enabled",
        })
        return apply_marine_point_mask(frame, purpose="rtofs_live_tile")

    def _last_good(self, bbox: BBox, error: str, *, tile_plan: dict[str, Any] | None = None, marine_mask: dict[str, Any] | None = None) -> tuple[OceanFieldFrame, ProviderStatus] | None:
        payload = self.cache.load(cache_key(bbox, self.depth_levels))
        if not payload:
            return None
        frame, status = frame_from_cache_payload(payload)
        status.cache_hit = True
        status.live_ok = True
        status.degraded = False
        status.error = error
        status.generated_time = now_iso()
        frame.metadata.update({
            "cache_status": "last_good_stitched_tiled_frame",
            "live_ok": True,
            "degraded": False,
            "error": error,
            "data_state": "last_good",
            "marine_land_mask": marine_mask or marine_mask_for_bbox(bbox),
            "rtofs_tiled_contract": tile_plan or self._ocean_tile_plan(bbox),
        })
        return apply_marine_point_mask(frame, purpose="rtofs_last_good_stitched_frame"), status

    def _no_data_frame(self, bbox: BBox, reason: str, marine_mask: dict[str, Any] | None = None, tile_plan: dict[str, Any] | None = None) -> tuple[OceanFieldFrame, ProviderStatus]:
        marine_mask = marine_mask or marine_mask_for_bbox(bbox)
        tile_plan = tile_plan or self._ocean_tile_plan(bbox)
        frame = OceanFieldFrame(
            bbox=bbox,
            valid_time=datetime.now(timezone.utc).isoformat(),
            grid_shape=(0, 0),
            depth_levels=[],
            channels={},
            metadata=self._metadata(bbox, "no_data:rtofs_ncep_tiled", live_ok=False, cache_status="none", degraded=False, error=reason, marine_mask=marine_mask, tile_plan=tile_plan),
        )
        frame.metadata.update({
            "grid_shape": [0, 0],
            "z_axis": {"kind": "depth_m_positive_down", "levels": []},
            "parser_status": "no_realtime_data",
            "live_status": "no_data",
            "data_state": "no_data",
            "rtofs_tiled_contract": tile_plan,
        })
        return frame, self._status_from_frame(frame, live_ok=False, cache_hit=False, degraded=False, source="no_data:rtofs_ncep_tiled", error=reason, marine_mask=marine_mask, tile_plan=tile_plan)

    def _metadata(self, bbox: BBox, source: str, live_ok: bool, cache_status: str, degraded: bool = False, error: str | None = None, marine_mask: dict[str, Any] | None = None, tile_plan: dict[str, Any] | None = None) -> dict[str, Any]:
        marine_mask = marine_mask or marine_mask_for_bbox(bbox)
        tile_plan = tile_plan or self._ocean_tile_plan(bbox)
        examples = tile_plan.get("request_url_examples") or []
        example = examples[0][0] if examples and isinstance(examples[0], list) else build_rtofs_url(self.settings.rtofs_nomads_base, bbox, self.depth_levels, self.settings.rtofs_max_grid_points)
        return {
            "provider": self.name,
            "source": source,
            "requested_bbox": bbox.model_dump(),
            "resolved_bbox": bbox.model_dump(),
            "valid_time": datetime.now(timezone.utc).isoformat(),
            "generated_time": now_iso(),
            "variable_aliases": aliases_used(),
            "grid_shape": "dynamic_from_tiled_frame",
            "depth_levels": self.depth_levels,
            "field_engine_depth_levels_m": self.settings.field_engine_depth_levels_m,
            "current_units": "m/s eastward/northward components; speed m/s; direction degrees from east counterclockwise",
            "provider_id": "rtofs_ncep_ocean",
            "source_url": source,
            "nomads_base": self.settings.rtofs_nomads_base,
            "product_files": list(SURFACE_FILES),
            "request_url_example": example,
            "aliases": aliases_used(),
            "normalized_channels": ["sst_c", "current_u", "current_v", "current_speed", "current_direction", "salinity", "depth_m", "bait_score", "bait_depth_m"],
            "parser_status": "bounded_rtofs_tile_parser_ok" if live_ok else "no_realtime_data",
            "field_engine": "tiled_bounded_rtofs_netcdf_parser" if live_ok else "tiled_rtofs_no_data",
            "live_status": "live_or_last_good_tiles" if live_ok else "no_data",
            "cache_status": cache_status,
            "live_ok": live_ok,
            "degraded": degraded,
            "error": error,
            "chlorophyll_hook": "future booster; not required for bait_score",
            "marine_land_mask": marine_mask,
            "rtofs_tiled_contract": tile_plan,
            "all_ocean_requests_tiled": True,
            "no_whole_viewport_rtofs_call": True,
        }

    def _status_from_frame(self, frame: OceanFieldFrame, live_ok: bool, cache_hit: bool, degraded: bool, source: str, error: str | None = None, marine_mask: dict[str, Any] | None = None, tile_plan: dict[str, Any] | None = None) -> ProviderStatus:
        marine_mask = marine_mask or frame.metadata.get("marine_land_mask") or marine_mask_for_bbox(frame.bbox)
        tile_plan = tile_plan or frame.metadata.get("rtofs_tiled_contract") or self._ocean_tile_plan(frame.bbox)
        return ProviderStatus(
            provider=self.name,
            mode=self.settings.rtofs_provider_mode,
            enabled=self.settings.rtofs_enabled,
            live_ok=live_ok,
            cache_hit=cache_hit,
            degraded=degraded,
            valid_time=frame.valid_time,
            generated_time=now_iso(),
            error=error,
            details={
                "source": source,
                "provider_id": "rtofs_ncep_ocean",
                "adapter_status": "tiled_live_or_last_good" if live_ok else "no_data",
                "parser_status": "bounded_RTOFS_tile_parser_ok" if live_ok else "no_realtime_data",
                "variable_aliases": aliases_used(),
                "grid_shape": list(frame.grid_shape),
                "depth_levels": frame.depth_levels,
                "marine_land_mask": marine_mask,
                "rtofs_tiled_contract": tile_plan,
                "all_ocean_requests_tiled": True,
                "no_whole_viewport_rtofs_call": True,
            },
        )


def get_rtofs_provider() -> RTOFSNCEPProvider:
    return RTOFSNCEPProvider()
