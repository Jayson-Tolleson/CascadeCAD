import hashlib
import math
import random
from app.schemas.scene import BBox
from app.services.field_truth_engine import get_field_truth_engine
from app.spatial.viewport_query import build_viewport_spatial
from app.services.marine_land_mask import marine_mask_for_bbox, marine_mask_for_boat_point, marine_point_filter_summary


def _seed_for_bbox(bbox: BBox) -> int:
    bucket = f'{round(bbox.west, 1)}:{round(bbox.south, 1)}:{round(bbox.east, 1)}:{round(bbox.north, 1)}'
    return int(hashlib.sha1(bucket.encode()).hexdigest()[:8], 16)


def _mean_current(bbox: BBox) -> tuple[float, float]:
    patch, _ = get_field_truth_engine().ocean_stream_patch(bbox)
    channels = patch.payload.get('channels', {})
    u_grid = channels.get('current_u', [[0]])
    v_grid = channels.get('current_v', [[0]])
    u_values = [float(value) for row in u_grid for value in row if float(value) != 0.0]
    v_values = [float(value) for row in v_grid for value in row if float(value) != 0.0]
    return (sum(u_values) / len(u_values), sum(v_values) / len(v_values)) if u_values and v_values else (0.0, 0.0)


def _candidate_is_water(lon: float, lat: float) -> bool:
    return bool(marine_mask_for_boat_point(lon, lat).get('should_render_boat', False))


def _jittered_water_anchor(rng: random.Random, lon: float, lat: float, bbox: BBox, max_tries: int = 12) -> tuple[float, float] | None:
    for attempt in range(max_tries):
        span_lon = max(0.006, (bbox.east - bbox.west) * 0.012)
        span_lat = max(0.006, (bbox.north - bbox.south) * 0.012)
        candidate_lon = lon + rng.uniform(-span_lon, span_lon) * (1 + attempt * 0.15)
        candidate_lat = lat + rng.uniform(-span_lat, span_lat) * (1 + attempt * 0.15)
        if bbox.west <= candidate_lon <= bbox.east and bbox.south <= candidate_lat <= bbox.north and _candidate_is_water(candidate_lon, candidate_lat):
            return candidate_lon, candidate_lat
    return None


def _random_water_point(rng: random.Random, bbox: BBox, max_tries: int = 48) -> tuple[float, float] | None:
    for _ in range(max_tries):
        lat = rng.uniform(bbox.south, bbox.north)
        lon = rng.uniform(bbox.west, bbox.east)
        if _candidate_is_water(lon, lat):
            return lon, lat
    return None


def generate_viewport_boats(bbox: BBox, count: int = 12) -> dict:
    marine_mask = marine_mask_for_bbox(bbox)
    if not marine_mask.get('should_query_ocean', True):
        return {
            'ok': True,
            'source': 'marine_land_mask_landlocked_no_boats',
            'boats': [],
            'count': 0,
            'marine_land_mask': marine_mask,
            'marine_point_mask': marine_point_filter_summary(0, 0, 'boats'),
        }
    rng = random.Random(_seed_for_bbox(bbox))
    spatial = build_viewport_spatial(bbox, tier='regional')
    u, v = _mean_current(bbox)
    heading = (math.degrees(math.atan2(v, u)) + 360) % 360 if (u or v) else 0
    waterbodies = spatial.get('waterbodies', [])
    boats = []
    checked = 0
    kept = 0
    attempts = 0
    max_attempts = max(count * 18, 60)
    while len(boats) < count and attempts < max_attempts:
        index = len(boats)
        attempts += 1
        source = 'viewport_seeded_open_water_entity'
        point = None
        if waterbodies and index < min(len(waterbodies), max(1, count // 2)):
            anchor = waterbodies[index % len(waterbodies)].get('label_point', {})
            lat = float(anchor.get('lat', (bbox.south + bbox.north) / 2))
            lon = float(anchor.get('lon', (bbox.west + bbox.east) / 2))
            point = _jittered_water_anchor(rng, lon, lat, bbox)
            source = 'spatial_waterbody_seeded_entity_land_masked'
        if point is None:
            point = _random_water_point(rng, bbox)
            source = 'viewport_seeded_open_water_entity_land_masked'
        checked += 1
        if point is None:
            continue
        lon, lat = point
        point_mask = marine_mask_for_boat_point(lon, lat)
        if not point_mask.get('should_render_boat', False):
            continue
        kept += 1
        boats.append({
            'id': f'boat_{_seed_for_bbox(bbox):x}_{index:02d}',
            'lat': round(lat, 6),
            'lon': round(lon, 6),
            'heading_deg': round((heading + rng.uniform(-20, 20)) % 360, 2),
            'current_u': round(u, 3),
            'current_v': round(v, 3),
            'safety': 'unknown',
            'safety_metadata': {'water_safe': True, 'boat_mask_checked': True, 'current_data_missing': not bool(u or v), 'marine_mask': point_mask},
            'model': 'polygon_heading_triangle',
            'model_hook': 'future_glb_model',
            'source': source,
        })
    return {
        'ok': True,
        'source': 'viewport_seeded_boat_entities_strict_land_masked',
        'boats': boats,
        'count': len(boats),
        'marine_land_mask': marine_mask,
        'marine_point_mask': marine_point_filter_summary(checked, kept, 'boats'),
    }
