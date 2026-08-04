from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.fields.base import AtmosphereFieldFrame
from app.providers.provider_status import ProviderStatus, now_iso
from app.schemas.scene import BBox
from app.services.provider_cache import ProviderCache

GFS_VARIABLES = [
    'Temperature_height_above_ground',
    'Relative_humidity_height_above_ground',
    'Dewpoint_temperature_height_above_ground',
    'Pressure_reduced_to_MSL_msl',
    'Total_cloud_cover_entire_atmosphere',
    'Low_cloud_cover_low_cloud',
    'Medium_cloud_cover_middle_cloud',
    'High_cloud_cover_high_cloud',
    'Precipitation_rate_surface',
    'u-component_of_wind_height_above_ground',
    'v-component_of_wind_height_above_ground',
]

CHANNEL_ALIASES = {
    'temperature': ['Temperature_height_above_ground', 'Temperature_surface', 'Temperature_height_above_ground_layer'],
    'humidity': ['Relative_humidity_height_above_ground', 'Relative_humidity_isobaric', 'Relative_humidity_entire_atmosphere'],
    'pressure': ['Pressure_reduced_to_MSL_msl', 'Pressure_surface'],
    'cloud_total': ['Total_cloud_cover_entire_atmosphere', 'Total_cloud_cover_convective_cloud', 'Cloud_cover_entire_atmosphere'],
    'low_cloud': ['Low_cloud_cover_low_cloud', 'Low_cloud_cover_low_cloud_Mixed_intervals_Average'],
    'mid_cloud': ['Medium_cloud_cover_middle_cloud', 'Medium_cloud_cover_middle_cloud_Mixed_intervals_Average'],
    'high_cloud': ['High_cloud_cover_high_cloud', 'High_cloud_cover_high_cloud_Mixed_intervals_Average'],
    'rain_rate': ['Precipitation_rate_surface', 'Convective_precipitation_rate_surface', 'Categorical_Rain_surface'],
    'wind_u': ['u-component_of_wind_height_above_ground', 'u-component_of_wind_isobaric'],
    'wind_v': ['v-component_of_wind_height_above_ground', 'v-component_of_wind_isobaric'],
}


def bbox_query_params(bbox: BBox) -> dict[str, str]:
    return {'west': str(bbox.west), 'east': str(bbox.east), 'south': str(bbox.south), 'north': str(bbox.north)}


def build_ncss_url(base_url: str, bbox: BBox, max_points: int) -> str:
    # NCSS Grid subset.  Keep horizStride=1 for regional/local fidelity; max_points
    # is retained as adapter metadata/contract and future emergency cap.
    query: dict[str, str | list[str]] = {
        **bbox_query_params(bbox),
        'time': 'present',
        'accept': 'netcdf4',
        'addLatLon': 'true',
        'horizStride': '1',
        'var': GFS_VARIABLES,
    }
    return f'{base_url}?{urllib.parse.urlencode(query, doseq=True)}'


def cache_key(bbox: BBox) -> str:
    return f'gfs_atmosphere_{bbox.west:.2f}_{bbox.south:.2f}_{bbox.east:.2f}_{bbox.north:.2f}'


def frame_to_cache_payload(frame: AtmosphereFieldFrame, status: ProviderStatus) -> dict[str, Any]:
    return {'frame': frame.model_dump(mode='json'), 'status': status.model_dump(mode='json')}


def frame_from_cache_payload(payload: dict[str, Any]) -> tuple[AtmosphereFieldFrame, ProviderStatus]:
    return AtmosphereFieldFrame(**payload['frame']), ProviderStatus(**payload['status'])


def _finite_float(value: Any, fallback: float = 0.0) -> float:
    try:
        f = float(value)
    except Exception:
        return fallback
    return f if math.isfinite(f) else fallback


def _project_cache_root() -> Path:
    root = os.environ.get('LFTR_CACHE_ROOT')
    if root:
        return Path(root).expanduser()
    return Path(__file__).resolve().parents[2]


class GFSNCSSProvider:
    name = 'gfs_ncss'

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cache = ProviderCache(self.settings.gfs_cache_dir)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            mode=self.settings.provider_mode,
            enabled=self.settings.gfs_enabled,
            generated_time=now_iso(),
            degraded=False,
            details={
                'base_url': self.settings.gfs_ncss_base_url,
                'ttl_seconds': self.settings.gfs_ttl_seconds,
                'max_grid_points': self.settings.gfs_max_grid_points,
                'adapter_status': 'bounded_ncss_netcdf_parser_enabled',
                'fallback_base_url': self.settings.gfs_ncss_fallback_url,
            },
        )

    def fetch_atmosphere(self, bbox: BBox) -> tuple[AtmosphereFieldFrame, ProviderStatus]:
        mode = self.settings.provider_mode
        if mode == 'mock' or not self.settings.gfs_enabled:
            return self._no_data_frame(bbox, reason='GFS provider not enabled for live parsing')
        try:
            return self._live_frame(bbox)
        except Exception as exc:  # provider boundary must never crash callers
            cached = self._last_good(bbox, str(exc))
            if cached:
                return cached
            return self._no_data_frame(bbox, reason=f'live GFS failed and no last-good cache exists: {exc}')

    def _candidate_base_urls(self) -> list[str]:
        # The working UCAR NCSS endpoint includes /ncss/grid/grib/.
        # Keep TwoD as a real-data fallback, not a mock/stub fallback.
        candidates = [
            self.settings.gfs_ncss_base_url,
            self.settings.gfs_ncss_fallback_url,
            'https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best',
            'https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/TwoD',
        ]
        clean: list[str] = []
        seen: set[str] = set()
        for url in candidates:
            value = str(url or '').strip()
            if not value or value in seen:
                continue
            clean.append(value)
            seen.add(value)
        return clean

    def _live_frame(self, bbox: BBox) -> tuple[AtmosphereFieldFrame, ProviderStatus]:
        errors: list[str] = []
        for base_url in self._candidate_base_urls():
            url = build_ncss_url(base_url, bbox, self.settings.gfs_max_grid_points)
            try:
                frame = self._fetch_and_parse_ncss(url, bbox)
            except Exception as exc:
                errors.append(f'{base_url}: {exc}')
                continue
            frame.metadata.update(self._metadata(bbox, url, live_ok=True, cache_status='live_parsed'))
            frame.metadata['grid_shape'] = list(frame.grid_shape)
            frame.metadata['parser_status'] = 'bounded_ncss_netcdf_parser_ok'
            frame.metadata['live_status'] = 'live_parsed'
            frame.metadata['cloud_feature_ready'] = True
            frame.metadata['configured_base_url'] = base_url
            frame.metadata['fallback_base_url'] = self.settings.gfs_ncss_fallback_url
            frame.metadata['candidate_base_urls'] = self._candidate_base_urls()
            status = self._status_from_frame(frame, live_ok=True, cache_hit=False, degraded=False, source=url, adapter_status='live_parsed')
            status.details['configured_base_url'] = base_url
            status.details['candidate_base_urls'] = self._candidate_base_urls()
            self.cache.save(cache_key(bbox), frame_to_cache_payload(frame, status))
            return frame, status
        raise RuntimeError('all live GFS NCSS URLs failed: ' + ' | '.join(errors))

    def _fetch_and_parse_ncss(self, url: str, bbox: BBox) -> AtmosphereFieldFrame:
        # Import here so local smoke checks can pass before installer pulls optional libs.
        import numpy as np  # type: ignore
        from netCDF4 import Dataset  # type: ignore

        with urllib.request.urlopen(url, timeout=self.settings.gfs_timeout_seconds) as response:
            raw = response.read()
        if not raw or raw[:32].lstrip().startswith(b'<'):
            raise RuntimeError('NCSS did not return NetCDF bytes')

        digest = hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]
        cache_dir = Path(self.cache.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        nc_path = cache_dir / f'ncss_{digest}.nc'
        nc_path.write_bytes(raw)

        with Dataset(str(nc_path), 'r') as ds:
            lat = self._coord_array(ds, ['lat', 'latitude', 'Lat', 'Latitude'])
            lon = self._coord_array(ds, ['lon', 'longitude', 'Lon', 'Longitude'])
            if lat is None or lon is None:
                raise RuntimeError('NCSS response missing lat/lon coordinates')
            channels: dict[str, list[list[float]]] = {}
            for channel, aliases in CHANNEL_ALIASES.items():
                arr = self._first_variable_array(ds, aliases)
                if arr is None:
                    arr = np.zeros((len(lat), len(lon)), dtype='float64')
                grid = self._normalize_channel(channel, arr)
                grid = self._orient_and_resample(grid, lat, lon)
                channels[channel] = grid.tolist()

        # Prefer explicit total_cloud, derive cloud density from all families and rain.
        total = np.asarray(channels.get('cloud_total') or channels.get('cloud_density'), dtype='float64')
        low = np.asarray(channels.get('low_cloud'), dtype='float64')
        mid = np.asarray(channels.get('mid_cloud'), dtype='float64')
        high = np.asarray(channels.get('high_cloud'), dtype='float64')
        rain = np.asarray(channels.get('rain_rate'), dtype='float64')
        density = np.clip(np.maximum.reduce([total, low * 0.86, mid * 0.80, high * 0.72]) + np.clip(rain, 0, 1) * 0.16, 0, 1)
        channels['cloud_density'] = np.round(density, 3).tolist()

        rows, cols = density.shape
        return AtmosphereFieldFrame(
            bbox=bbox,
            valid_time=datetime.now(timezone.utc).isoformat(),
            grid_shape=(int(rows), int(cols)),
            levels=['low', 'mid', 'high'],
            channels=channels,
            metadata={
                'source': 'gfs_ncss_live_parsed',
                'source_url': url,
                'degraded': False,
                'field_engine': 'bounded_gfs_ncss_netcdf_parser',
                'grid_shape': [int(rows), int(cols)],
                'z_axis': {'kind': 'altitude_m', 'levels_m': [900, 4200, 9800]},
                'cloud_feature_ready': True,
                'coordinate_model': 'ncss_lat_lon_grid_resampled_south_to_north',
            },
        )

    def _coord_array(self, ds: Any, names: list[str]):
        import numpy as np  # type: ignore
        for name in names:
            if name in ds.variables:
                arr = np.asarray(ds.variables[name][:], dtype='float64')
                if arr.ndim == 2:
                    # Common curvilinear NCSS lat/lon; reduce to monotonic axes.
                    if 'lat' in name.lower():
                        return arr[:, 0]
                    return arr[0, :]
                if arr.ndim == 1:
                    return arr
        return None

    def _first_variable_array(self, ds: Any, aliases: list[str]):
        import numpy as np  # type: ignore
        for alias in aliases:
            if alias not in ds.variables:
                continue
            var = ds.variables[alias]
            arr = np.asarray(var[:], dtype='float64')
            # Drop time/level axes by taking first available slice until 2D remains.
            while arr.ndim > 2:
                arr = arr[0]
            if arr.ndim == 1:
                arr = arr.reshape((1, arr.shape[0]))
            if arr.ndim == 2:
                fill_value = getattr(var, '_FillValue', None)
                missing = getattr(var, 'missing_value', None)
                if fill_value is not None:
                    arr = np.where(arr == float(fill_value), np.nan, arr)
                if missing is not None:
                    arr = np.where(arr == float(missing), np.nan, arr)
                return arr
        return None

    def _normalize_channel(self, channel: str, arr: Any):
        import numpy as np  # type: ignore
        grid = np.asarray(arr, dtype='float64')
        grid = np.nan_to_num(grid, nan=0.0, posinf=0.0, neginf=0.0)
        if channel in {'cloud_total', 'low_cloud', 'mid_cloud', 'high_cloud', 'humidity'}:
            if float(np.nanmax(grid)) > 1.5:
                grid = grid / 100.0
            return np.round(np.clip(grid, 0.0, 1.0), 3)
        if channel == 'rain_rate':
            # GFS precip rate is commonly kg m-2 s-1. Scale lightly for visual intensity.
            if float(np.nanmax(grid)) < 1.0:
                grid = grid * 900.0
            else:
                grid = grid / max(1.0, float(np.nanmax(grid)))
            return np.round(np.clip(grid, 0.0, 1.0), 3)
        if channel == 'temperature':
            if float(np.nanmean(grid)) > 180.0:
                grid = grid - 273.15
            return np.round(grid, 3)
        if channel == 'pressure':
            if float(np.nanmean(grid)) > 2000.0:
                grid = grid / 100.0
            return np.round(grid, 3)
        return np.round(grid, 3)

    def _orient_and_resample(self, grid: Any, lat: Any, lon: Any):
        import numpy as np  # type: ignore
        arr = np.asarray(grid, dtype='float64')
        lat_arr = np.asarray(lat, dtype='float64')
        lon_arr = np.asarray(lon, dtype='float64')
        if arr.shape[0] == lon_arr.size and arr.shape[1] == lat_arr.size:
            arr = arr.T
        if lat_arr.size >= 2 and lat_arr[0] > lat_arr[-1]:
            arr = arr[::-1, :]
        # If NCSS returns 0..360 longitudes, keep array order; bbox mapping handles requested span.
        max_size = max(12, int(self.settings.field_engine_grid_size))
        rows, cols = arr.shape
        if rows <= max_size and cols <= max_size:
            return arr
        row_idx = np.linspace(0, rows - 1, max_size).round().astype(int) if rows > max_size else np.arange(rows)
        col_idx = np.linspace(0, cols - 1, max_size).round().astype(int) if cols > max_size else np.arange(cols)
        return arr[np.ix_(row_idx, col_idx)]

    def _last_good(self, bbox: BBox, error: str) -> tuple[AtmosphereFieldFrame, ProviderStatus] | None:
        payload = self.cache.load(cache_key(bbox))
        if not payload:
            return None
        frame, status = frame_from_cache_payload(payload)
        # Last-good parsed GFS is allowed to render, but marked as cache-hit/stale instead of mock.
        status.cache_hit = True
        status.live_ok = True
        status.degraded = False
        status.error = error
        status.generated_time = now_iso()
        frame.metadata.update({'cache_status': 'last_good_live_parsed', 'live_ok': True, 'degraded': False, 'error': error, 'parser_status': 'bounded_ncss_netcdf_parser_last_good'})
        return frame, status

    def _no_data_frame(self, bbox: BBox, reason: str) -> tuple[AtmosphereFieldFrame, ProviderStatus]:
        frame = AtmosphereFieldFrame(
            bbox=bbox,
            valid_time=datetime.now(timezone.utc).isoformat(),
            grid_shape=(0, 0),
            levels=[],
            channels={},
            metadata=self._metadata(bbox, 'no_data:gfs_ncss', live_ok=False, cache_status='none', degraded=False, error=reason),
        )
        frame.metadata.update({
            'grid_shape': [0, 0],
            'parser_status': 'no_realtime_data',
            'live_status': 'no_data',
            'cloud_feature_ready': False,
            'data_state': 'no_data',
        })
        return frame, self._status_from_frame(frame, live_ok=False, cache_hit=False, degraded=False, source='no_data:gfs_ncss', error=reason, adapter_status='no_data')

    def _metadata(self, bbox: BBox, source: str, live_ok: bool, cache_status: str, degraded: bool = False, error: str | None = None) -> dict[str, Any]:
        return {
            'provider': self.name,
            'source': source,
            'requested_bbox': bbox.model_dump(),
            'resolved_bbox': bbox.model_dump(),
            'valid_time': datetime.now(timezone.utc).isoformat(),
            'generated_time': now_iso(),
            'variables': GFS_VARIABLES,
            'grid_shape': 'dynamic_from_frame',
            'provider_id': 'gfs_ncss_atmosphere',
            'source_url': source,
            'configured_base_url': self.settings.gfs_ncss_base_url,
            'fallback_base_url': self.settings.gfs_ncss_fallback_url,
            'request_url_example': build_ncss_url(self.settings.gfs_ncss_base_url, bbox, self.settings.gfs_max_grid_points),
            'variables_requested': GFS_VARIABLES,
            'normalized_channels': ['cloud_density', 'cloud_total', 'low_cloud', 'mid_cloud', 'high_cloud', 'rain_rate', 'wind_u', 'wind_v', 'humidity', 'temperature', 'pressure'],
            'units': {'wind_u': 'm/s eastward', 'wind_v': 'm/s northward'},
            'parser_status': 'bounded_ncss_netcdf_parser_ok' if live_ok else 'no_realtime_data',
            'field_engine': 'bounded_gfs_ncss_netcdf_parser' if live_ok else 'none',
            'live_status': 'live_parsed' if live_ok else 'no_data',
            'cache_status': cache_status,
            'live_ok': live_ok,
            'degraded': degraded,
            'error': error,
        }

    def _status_from_frame(self, frame: AtmosphereFieldFrame, live_ok: bool, cache_hit: bool, degraded: bool, source: str, error: str | None = None, adapter_status: str = 'live_parsed') -> ProviderStatus:
        return ProviderStatus(
            provider=self.name,
            mode=self.settings.provider_mode,
            enabled=self.settings.gfs_enabled,
            live_ok=live_ok,
            cache_hit=cache_hit,
            degraded=degraded,
            valid_time=frame.valid_time,
            generated_time=now_iso(),
            error=error,
            details={'source': source, 'variables': GFS_VARIABLES, 'grid_shape': list(frame.grid_shape), 'adapter_status': adapter_status},
        )


def get_gfs_provider() -> GFSNCSSProvider:
    return GFSNCSSProvider()
