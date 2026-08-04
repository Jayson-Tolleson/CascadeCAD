from __future__ import annotations

from collections import deque
from hashlib import sha1
from typing import Any

from app.fields.base import AtmosphereFieldFrame

CloudFamily = str
CloudSize = str


def _feature_digest(*parts: object) -> str:
    raw = ':'.join(str(part) for part in parts)
    return sha1(raw.encode('utf-8')).hexdigest()


def _particle_budget(size: CloudSize, family: CloudFamily, density: float, rain: float, area_cells: int) -> int:
    base = {'micro': 12, 'small': 24, 'medium': 44, 'large': 78, 'massive': 120}[size]
    if family in {'stratus', 'marine-stratus'}:
        base += 22
    if family == 'cirrus':
        base = int(base * 0.72)
    if family == 'cumulonimbus':
        base += 34 + int(rain * 32)
    budget = int(base + density * 30 + min(38, area_cells / 18))
    return max(8, min(220, budget))


def _grid(frame: AtmosphereFieldFrame, name: str, fallback: float = 0.0) -> list[list[float]]:
    rows, cols = frame.grid_shape
    value = frame.channels.get(name)
    if value:
        return value
    return [[fallback for _ in range(cols)] for _ in range(rows)]


def _cell_lon_lat(frame: AtmosphereFieldFrame, row: int, col: int) -> tuple[float, float]:
    rows, cols = frame.grid_shape
    x = 0.0 if cols <= 1 else col / (cols - 1)
    y = 0.0 if rows <= 1 else row / (rows - 1)
    lon = frame.bbox.west + (frame.bbox.east - frame.bbox.west) * x
    lat = frame.bbox.south + (frame.bbox.north - frame.bbox.south) * y
    return lon, lat


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _size(area_cells: int, rows: int, cols: int, density: float) -> CloudSize:
    ratio = area_cells / max(1, rows * cols)
    score = max(density, ratio * 8)
    if ratio > 0.13 or score > 0.92:
        return 'massive'
    if ratio > 0.055 or score > 0.72:
        return 'large'
    if ratio > 0.018 or score > 0.50:
        return 'medium'
    if ratio > 0.006 or score > 0.30:
        return 'small'
    return 'micro'


def _family(density: float, low: float, mid: float, high: float, rain: float, humidity: float, area_ratio: float) -> CloudFamily:
    """Classify into meteorology-facing cloud families.

    These are intentionally renderer-friendly in Pass 3: cumulus uses a puff-cluster
    shape, stratus/marine-stratus use flat sheets, cirrus uses high wispy streaks,
    and cumulonimbus uses a darker vertically stacked body.
    """
    if rain > 0.42 or (density > 0.80 and humidity > 0.55):
        return 'cumulonimbus'
    if low > 0.44 and humidity > 0.48 and area_ratio > 0.008:
        return 'marine-stratus'
    if high > low and high > mid and density < 0.62 and rain < 0.25:
        return 'cirrus'
    if density > 0.56 or low > 0.50 or area_ratio > 0.028:
        return 'stratus'
    return 'cumulus'


def _render_style(family: CloudFamily) -> str:
    return {
        'cumulus': 'puff-cluster',
        'stratus': 'flat-sheet',
        'cirrus': 'wispy-streak',
        'marine-stratus': 'coastal-blanket',
        'cumulonimbus': 'tower-stack',
    }.get(family, 'puff-cluster')


def _altitude_m(family: CloudFamily, density: float, high: float) -> float:
    if family == 'marine-stratus':
        return 600 + density * 1250
    if family == 'stratus':
        return 1300 + density * 3300
    if family == 'cirrus':
        return 7800 + high * 5600
    if family == 'cumulonimbus':
        return 3200 + density * 11200
    return 2400 + density * 5600


def _thickness_m(family: CloudFamily, density: float, rain: float) -> float:
    if family == 'marine-stratus':
        return 220 + density * 420
    if family == 'stratus':
        return 450 + density * 900
    if family == 'cirrus':
        return 180 + density * 260
    if family == 'cumulonimbus':
        return 2600 + density * 8200 + rain * 2600
    return 850 + density * 2200


def _scale(size: CloudSize, family: CloudFamily, area_cells: int) -> float:
    base = {'micro': 0.70, 'small': 1.05, 'medium': 1.48, 'large': 2.05, 'massive': 2.85}[size]
    if family == 'cirrus':
        base *= 1.28
    if family == 'cumulonimbus':
        base *= 1.18
    if family in {'stratus', 'marine-stratus'}:
        base *= 1.08
    return round(base + min(0.55, area_cells / 900), 3)


def _opacity(density: float, rain: float, family: CloudFamily) -> float:
    base = 0.18 + density * 0.58 + rain * 0.20
    if family == 'cirrus':
        base *= 0.58
    if family == 'cumulonimbus':
        base += 0.12
    if family == 'marine-stratus':
        base += 0.05
    return round(min(0.94, max(0.12, base)), 3)


def extract_cloud_features(frame: AtmosphereFieldFrame, threshold: float = 0.22, max_features: int = 54) -> dict[str, Any]:
    """Extract soft cloud render features from a normalized atmosphere scalar field.

    Live/last-good provider frames create features. Honest no-data frames create an
    empty feature patch without synthetic clouds.
    """
    rows, cols = frame.grid_shape
    if rows <= 0 or cols <= 0 or not frame.channels:
        return {
            'ok': True,
            'source': frame.metadata.get('source', 'no_data'),
            'valid_time': frame.valid_time,
            'bbox': frame.bbox.model_dump(mode='json'),
            'grid_shape': list(frame.grid_shape),
            'threshold': threshold,
            'feature_count': 0,
            'families': [],
            'sizes': [],
            'features': [],
            'metadata': {'data_state': frame.metadata.get('data_state', 'no_data')},
        }
    density_grid = _grid(frame, 'cloud_density')
    low_grid = _grid(frame, 'low_cloud')
    mid_grid = _grid(frame, 'mid_cloud')
    high_grid = _grid(frame, 'high_cloud')
    rain_grid = _grid(frame, 'rain_rate')
    humidity_grid = _grid(frame, 'humidity', 0.55)
    wind_u_grid = _grid(frame, 'wind_u')
    wind_v_grid = _grid(frame, 'wind_v')

    cloudy = [[False for _ in range(cols)] for _ in range(rows)]
    cell_family: list[list[CloudFamily | None]] = [[None for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            signal = max(density_grid[row][col], low_grid[row][col] * 0.92, mid_grid[row][col] * 0.86, high_grid[row][col] * 0.80)
            if signal < threshold:
                continue
            cloudy[row][col] = True
            # Family is assigned per cell before component extraction.  That keeps a
            # huge cloud deck from collapsing into one generic feature and lets
            # cumulus, stratus, cirrus, marine-stratus, and cumulonimbus areas keep
            # their own shape grammar when the frontend renders them.
            cell_family[row][col] = _family(
                density_grid[row][col],
                low_grid[row][col],
                mid_grid[row][col],
                high_grid[row][col],
                rain_grid[row][col],
                humidity_grid[row][col],
                1 / max(1, rows * cols),
            )

    seen = [[False for _ in range(cols)] for _ in range(rows)]
    components: list[tuple[CloudFamily, list[tuple[int, int]]]] = []
    for row in range(rows):
        for col in range(cols):
            family_seed = cell_family[row][col]
            if seen[row][col] or not cloudy[row][col] or family_seed is None:
                continue
            queue: deque[tuple[int, int]] = deque([(row, col)])
            seen[row][col] = True
            cells: list[tuple[int, int]] = []
            while queue:
                r, c = queue.popleft()
                cells.append((r, c))
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nr, nc = r + dr, c + dc
                    if nr < 0 or nr >= rows or nc < 0 or nc >= cols or seen[nr][nc] or not cloudy[nr][nc]:
                        continue
                    if cell_family[nr][nc] != family_seed:
                        continue
                    seen[nr][nc] = True
                    queue.append((nr, nc))
            components.append((family_seed, cells))

    components.sort(key=lambda item: len(item[1]), reverse=True)
    features: list[dict[str, Any]] = []
    for index, (family_seed, cells) in enumerate(components[:max_features]):
        rs = [r for r, _ in cells]
        cs = [c for _, c in cells]
        lons_lats = [_cell_lon_lat(frame, r, c) for r, c in cells]
        densities = [density_grid[r][c] for r, c in cells]
        lows = [low_grid[r][c] for r, c in cells]
        mids = [mid_grid[r][c] for r, c in cells]
        highs = [high_grid[r][c] for r, c in cells]
        rains = [rain_grid[r][c] for r, c in cells]
        hums = [humidity_grid[r][c] for r, c in cells]
        wus = [wind_u_grid[r][c] for r, c in cells]
        wvs = [wind_v_grid[r][c] for r, c in cells]
        density = _avg(densities)
        low = _avg(lows)
        mid = _avg(mids)
        high = _avg(highs)
        rain = _avg(rains)
        humidity = _avg(hums)
        area_ratio = len(cells) / max(1, rows * cols)
        family = family_seed
        size = _size(len(cells), rows, cols, max(density, low, mid, high, rain))
        west, east = min(lon for lon, _ in lons_lats), max(lon for lon, _ in lons_lats)
        south, north = min(lat for _, lat in lons_lats), max(lat for _, lat in lons_lats)
        # Density-weighted center makes the feature anchor visually sit inside the mass.
        weight_sum = sum(densities) or len(cells)
        center_lon = sum(lon * max(0.01, d) for (lon, _), d in zip(lons_lats, densities)) / weight_sum
        center_lat = sum(lat * max(0.01, d) for (_, lat), d in zip(lons_lats, densities)) / weight_sum
        digest = _feature_digest(
            frame.valid_time, family, size, min(rs), max(rs), min(cs), max(cs),
            round(center_lon, 4), round(center_lat, 4), len(cells), round(density, 3), round(rain, 3),
        )
        budget = _particle_budget(size, family, density, rain, len(cells))
        cells_per_particle = max(1, round(len(cells) / max(1, budget)))
        feature_id = f'cloud-feature-{index + 1:03d}-{digest[:8]}'
        render_style = _render_style(family)
        features.append({
            'id': feature_id,
            'family': family,
            'size': size,
            'centroid': {'lon': round(center_lon, 6), 'lat': round(center_lat, 6)},
            'bbox': {'west': round(west, 6), 'south': round(south, 6), 'east': round(east, 6), 'north': round(north, 6)},
            'grid_bbox': {'row_min': min(rs), 'row_max': max(rs), 'col_min': min(cs), 'col_max': max(cs)},
            'area_cells': len(cells),
            'area_ratio': round(area_ratio, 5),
            'density': round(density, 3),
            'density_max': round(max(densities), 3),
            'low_cloud': round(low, 3),
            'mid_cloud': round(mid, 3),
            'high_cloud': round(high, 3),
            'rain_rate': round(rain, 3),
            'rain_factor': round(rain, 3),
            'humidity': round(humidity, 3),
            'wind_u': round(_avg(wus), 3),
            'wind_v': round(_avg(wvs), 3),
            'altitude_m': round(_altitude_m(family, density, high), 1),
            'render_style': render_style,
            'thickness_m': round(_thickness_m(family, density, rain), 1),
            'opacity': _opacity(density, rain, family),
            'scale': _scale(size, family, len(cells)),
            'particle_seed': digest[:16],
            'particle_budget': budget,
            'cells_per_particle': cells_per_particle,
            'title': f'{family} {size} · {render_style} · cloud {round(density * 100)}% · cells {len(cells)} · particles {budget}',
        })

    return {
        'ok': True,
        'source': frame.metadata.get('source', 'gfs_ncss_live_parsed'),
        'valid_time': frame.valid_time,
        'bbox': frame.bbox.model_dump(mode='json'),
        'grid_shape': list(frame.grid_shape),
        'threshold': threshold,
        'feature_count': len(features),
        'families': sorted({feature['family'] for feature in features}),
        'sizes': sorted({feature['size'] for feature in features}),
        'features': features,
    }
