from __future__ import annotations

from collections import deque
from typing import Any
from app.fields.base import OceanFieldFrame
from app.services.marine_land_mask import marine_mask_for_bbox, marine_mask_for_point, marine_point_filter_summary


def _grid(frame: OceanFieldFrame, name: str, fallback: float = 0.0) -> list[list[float]]:
    rows, cols = frame.grid_shape
    grid = frame.channels.get(name)
    if grid:
        return grid
    return [[fallback for _ in range(cols)] for _ in range(rows)]


def _cell_lon_lat(frame: OceanFieldFrame, row: int, col: int) -> tuple[float, float]:
    rows, cols = frame.grid_shape
    x = 0.0 if cols <= 1 else col / (cols - 1)
    y = 0.0 if rows <= 1 else row / (rows - 1)
    lon = frame.bbox.west + (frame.bbox.east - frame.bbox.west) * x
    lat = frame.bbox.south + (frame.bbox.north - frame.bbox.south) * y
    return lon, lat


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stable_cell_id(prefix: str, lon: float, lat: float, depth_m: float = 0.0) -> str:
    # Keep feature IDs stable across successive RTOFS/PostGIS refreshes.  The
    # frontend morph reducers depend on stable IDs so schools/particles move
    # instead of being deleted/recreated on every SSE cycle.
    return f"{prefix}-{round(lon, 2):+.2f}-{round(lat, 2):+.2f}-z{round(depth_m / 10) * 10:.0f}".replace("+", "p").replace("-", "m").replace(".", "_")


def _current_vectors(frame: OceanFieldFrame, max_vectors: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, cols = frame.grid_shape
    u = _grid(frame, "current_u")
    v = _grid(frame, "current_v")
    speed = _grid(frame, "current_speed")
    stride = max(1, int(((rows * cols) / max(1, max_vectors)) ** 0.5))
    vectors: list[dict[str, Any]] = []
    checked = 0
    kept = 0
    for row in range(0, rows, stride):
        for col in range(0, cols, stride):
            lon, lat = _cell_lon_lat(frame, row, col)
            checked += 1
            if not marine_mask_for_point(lon, lat).get("should_render_ocean", True):
                continue
            kept += 1
            vectors.append({
                "id": _stable_cell_id("current-vector", lon, lat, 0.0),
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "u": round(u[row][col], 3),
                "v": round(v[row][col], 3),
                "speed": round(speed[row][col], 3),
                "depth_m": 0.0,
                "marine_mask": "water_or_allowed_coastal",
            })
            if len(vectors) >= max_vectors:
                return vectors, marine_point_filter_summary(checked, kept, "current_vectors")
    return vectors, marine_point_filter_summary(checked, kept, "current_vectors")

def _bait_clusters(frame: OceanFieldFrame, threshold: float, max_clusters: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, cols = frame.grid_shape
    bait = _grid(frame, "bait_score")
    bait_depth = _grid(frame, "bait_depth_m")
    checked_cells = rows * cols
    water_allowed = [[bool(marine_mask_for_point(*_cell_lon_lat(frame, row, col)).get("should_render_ocean", True)) for col in range(cols)] for row in range(rows)]
    cloudy = [[water_allowed[row][col] and bait[row][col] >= threshold for col in range(cols)] for row in range(rows)]
    seen = [[False for _ in range(cols)] for _ in range(rows)]
    components: list[list[tuple[int, int]]] = []
    for row in range(rows):
        for col in range(cols):
            if seen[row][col] or not cloudy[row][col]:
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
                    seen[nr][nc] = True
                    queue.append((nr, nc))
            components.append(cells)
    components.sort(key=len, reverse=True)
    clusters: list[dict[str, Any]] = []
    kept_cells = 0
    for index, cells in enumerate(components[:max_clusters]):
        lons_lats = [_cell_lon_lat(frame, r, c) for r, c in cells]
        scores = [bait[r][c] for r, c in cells]
        depths = [bait_depth[r][c] for r, c in cells]
        weight_sum = sum(scores) or len(cells)
        center_lon = sum(lon * max(0.01, score) for (lon, _), score in zip(lons_lats, scores)) / weight_sum
        center_lat = sum(lat * max(0.01, score) for (_, lat), score in zip(lons_lats, scores)) / weight_sum
        if not marine_mask_for_point(center_lon, center_lat).get("should_render_ocean", True):
            continue
        kept_cells += len(cells)
        avg_depth = round(_avg(depths), 3)
        max_depth = round(max(depths), 3) if depths else avg_depth
        stable_id = _stable_cell_id("bait-cluster", center_lon, center_lat, avg_depth)
        particle_budget = max(18, min(112, int(len(cells) * 1.75 + max(scores) * 42)))
        if particle_budget % 2:
            particle_budget += 1
        clusters.append({
            "id": stable_id,
            "centroid": {"lon": round(center_lon, 6), "lat": round(center_lat, 6)},
            "bbox": {
                "west": round(min(lon for lon, _ in lons_lats), 6),
                "south": round(min(lat for _, lat in lons_lats), 6),
                "east": round(max(lon for lon, _ in lons_lats), 6),
                "north": round(max(lat for _, lat in lons_lats), 6),
            },
            "area_cells": len(cells),
            "score": round(_avg(scores), 3),
            "score_max": round(max(scores), 3),
            "depth_m": avg_depth,
            "depth_min_m": round(min(depths), 3) if depths else avg_depth,
            "depth_max_m": max_depth,
            "particle_budget": particle_budget,
            "family": "bait_cluster",
            "render_hint": "transparent_orange_school_shell_with_mirror_silver_white_4_8in_particles_depth_aware_morph",
            "marine_mask": "water_or_allowed_coastal",
        })
    return clusters, marine_point_filter_summary(checked_cells, kept_cells, "bait_clusters")

def extract_ocean_features(frame: OceanFieldFrame, max_current_vectors: int = 72, bait_threshold: float = 0.58, max_bait_clusters: int = 48) -> dict[str, Any]:
    if frame.grid_shape[0] <= 0 or frame.grid_shape[1] <= 0 or not frame.channels:
        return {
            "ok": True,
            "source": frame.metadata.get("source", "no_data"),
            "valid_time": frame.valid_time,
            "bbox": frame.bbox.model_dump(mode="json"),
            "grid_shape": list(frame.grid_shape),
            "depth_levels": frame.depth_levels,
            "current_vector_count": 0,
            "bait_cluster_count": 0,
            "current_vectors": [],
            "bait_clusters": [],
            "metadata": {"data_state": frame.metadata.get("data_state", "no_data")},
        }
    vectors, vector_mask = _current_vectors(frame, max_current_vectors)
    bait_clusters, bait_mask = _bait_clusters(frame, bait_threshold, max_bait_clusters)
    return {
        "ok": True,
        "source": frame.metadata.get("source", "rtofs_ncep_live_parsed"),
        "valid_time": frame.valid_time,
        "bbox": frame.bbox.model_dump(mode="json"),
        "grid_shape": list(frame.grid_shape),
        "depth_levels": frame.depth_levels,
        "current_vector_count": len(vectors),
        "bait_cluster_count": len(bait_clusters),
        "current_vectors": vectors,
        "bait_clusters": bait_clusters,
        "metadata": {
            "field_engine": "xyz_scalar_field_pass1",
            "z_axis": frame.metadata.get("z_axis"),
            "surface_channels": list(frame.channels.keys()),
            "future_render_contract": "persistent ocean truth: frontend retains, advects, and morphs bait schools/boat hazards from stable PostGIS/RTOFS feature IDs; raw ocean.field.patch remains available",
            "marine_land_mask": marine_mask_for_bbox(frame.bbox),
            "current_vector_mask": vector_mask,
            "bait_cluster_mask": bait_mask,
        },
    }
