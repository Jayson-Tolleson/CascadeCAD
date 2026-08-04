from app.core.config import get_settings
from app.schemas.scene import BBox
from app.spatial.usgs.arcgis_rest import query_arcgis_geojson
from app.spatial.usgs.cache import USGSIngestCache, batch_id
from app.spatial.usgs.geojson_loader import load_geojson
from app.spatial.usgs.normalizer import normalize_geojson
from app.spatial.usgs.waterbody_types import LFTRWaterbody


def mock_geojson() -> dict:
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'id': 'mock_lake_socal_001', 'name': 'Mock SoCal Reservoir', 'kind': 'reservoir', 'area_km2': 2.4}, 'geometry': {'type': 'Polygon', 'coordinates': [[[-118.35, 34.08], [-118.30, 34.08], [-118.30, 34.12], [-118.35, 34.12], [-118.35, 34.08]]]}},
        {'type': 'Feature', 'properties': {'id': 'mock_lake_florida_001', 'name': 'Mock Florida Lake', 'kind': 'lake', 'area_km2': 6.2}, 'geometry': {'type': 'Polygon', 'coordinates': [[[-80.85, 26.90], [-80.75, 26.90], [-80.75, 27.00], [-80.85, 27.00], [-80.85, 26.90]]]}},
        {'type': 'Feature', 'properties': {'id': 'mock_pond_generic_001', 'name': 'Generic Mock Pond', 'kind': 'pond', 'area_km2': 0.08}, 'geometry': {'type': 'Polygon', 'coordinates': [[[-120.02, 35.00], [-120.00, 35.00], [-120.00, 35.02], [-120.02, 35.02], [-120.02, 35.00]]]}}
    ]}


def _bbox_filter(items: list[LFTRWaterbody], bbox: BBox) -> list[LFTRWaterbody]:
    def intersects(item: LFTRWaterbody) -> bool:
        west, south, east, north = item.bbox
        return not (east < bbox.west or west > bbox.east or north < bbox.south or south > bbox.north)
    return [item for item in items if intersects(item)]


def load_cached_mock_waterbodies(bbox: BBox, tier: str = 'regional') -> list[dict]:
    batch = 'mock_cache_fallback'
    return [item.viewport_dict(include_geometry=tier != 'global') for item in _bbox_filter(normalize_geojson(mock_geojson(), 'mock', batch), bbox)]


def ingest_waterbodies(bbox: BBox, source_family: str | None = None, load_postgis: bool = True) -> dict:
    settings = get_settings()
    family = source_family or settings.usgs_source_family
    cache = USGSIngestCache()
    batch = batch_id(family, bbox)
    diagnostics = {'source_family': family, 'batch_id': batch, 'postgis_loaded': False, 'errors': []}
    try:
        if family == 'mock' or family in {'3dhp', 'nhdplus_hr', 'nhd'} and not settings.usgs_enabled:
            raw = mock_geojson()
        elif family == 'geojson':
            if not settings.usgs_geojson_path:
                raise RuntimeError('LFTR_USGS_GEOJSON_PATH is not configured')
            raw = load_geojson(settings.usgs_geojson_path)
        elif family == 'arcgis_rest':
            raw = query_arcgis_geojson(bbox)
        elif family == 'shapefile_zip':
            raise RuntimeError('shapefile_zip ingest requires optional geospatial dependencies; not required for app startup')
        else:
            raw = mock_geojson()
            diagnostics['errors'].append(f'source family {family} unavailable; used mock fallback')
        cache.write_json('raw', batch, raw)
        normalized = _bbox_filter(normalize_geojson(raw, family if family != 'mock' else 'mock', batch), bbox)
        cache.write_json('normalized', batch, [item.model_dump(mode='json') for item in normalized])
        if load_postgis and normalized:
            from app.spatial.postgis_repository import PostGISSpatialRepository
            repo = PostGISSpatialRepository()
            if repo.available():
                diagnostics['postgis_loaded'] = True
                repo.upsert_waterbodies(normalized)
        summary = {'ok': True, 'batch_id': batch, 'source_family': family, 'count': len(normalized), 'waterbodies': [item.viewport_dict() for item in normalized], 'diagnostics': diagnostics}
        cache.write_json('diagnostics', batch, summary)
        return summary
    except Exception as exc:
        diagnostics['errors'].append(str(exc))
        fallback = _bbox_filter(normalize_geojson(mock_geojson(), 'mock', batch), bbox)
        summary = {'ok': False, 'batch_id': batch, 'source_family': family, 'count': len(fallback), 'waterbodies': [item.viewport_dict() for item in fallback], 'diagnostics': diagnostics, 'fallback': 'mock'}
        cache.write_json('diagnostics', batch, summary)
        return summary
