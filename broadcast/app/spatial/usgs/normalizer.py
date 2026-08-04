import hashlib
import json
import re
from app.spatial.usgs.sources import source_label
from app.spatial.usgs.waterbody_types import LFTRWaterbody


def _coords(geometry: dict) -> list[tuple[float, float]]:
    if geometry.get('type') == 'Polygon':
        return [(float(lon), float(lat)) for lon, lat in geometry.get('coordinates', [[]])[0]]
    if geometry.get('type') == 'MultiPolygon':
        return [(float(lon), float(lat)) for lon, lat in geometry.get('coordinates', [[[[]]]])[0][0]]
    return []


def geometry_bbox(geometry: dict) -> list[float]:
    pts = _coords(geometry)
    if not pts:
        return [0, 0, 0, 0]
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return [min(lons), min(lats), max(lons), max(lats)]


def label_point(geometry: dict) -> dict[str, float]:
    west, south, east, north = geometry_bbox(geometry)
    return {'lon': round((west + east) / 2, 6), 'lat': round((south + north) / 2, 6)}


def area_km2_from_bbox(bbox: list[float]) -> float:
    west, south, east, north = bbox
    return round(abs((east - west) * 111.0 * (north - south) * 111.0), 4)


def normalize_kind(value: str | None) -> str:
    text = (value or '').lower()
    if 'reservoir' in text:
        return 'reservoir'
    if 'pond' in text:
        return 'pond'
    if 'river' in text or 'stream' in text:
        return 'river'
    if 'canal' in text:
        return 'canal'
    if 'wetland' in text or 'swamp' in text or 'marsh' in text:
        return 'wetland'
    if 'bay' in text:
        return 'bay'
    if 'lake' in text:
        return 'lake'
    return 'unknown_waterbody'


def stable_id_for(source_family: str, properties: dict, geometry: dict, name: str, area_km2: float) -> str:
    native = properties.get('permanent_identifier') or properties.get('Permanent_Identifier') or properties.get('gnis_id') or properties.get('GNIS_ID') or properties.get('nhdplusid') or properties.get('NHDPlusID') or properties.get('comid') or properties.get('COMID') or properties.get('objectid') or properties.get('OBJECTID') or properties.get('id')
    if native:
        return f'{source_family}_{native}'.lower().replace(' ', '_')
    anchor = label_point(geometry)
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_') or 'unnamed_waterbody'
    digest = hashlib.sha1(json.dumps(geometry, sort_keys=True).encode()).hexdigest()[:10]
    return f'{source_family}_{slug}_{round(anchor["lon"], 3)}_{round(anchor["lat"], 3)}_{round(area_km2, 1)}_{digest}'.replace('-', 'm')


def normalize_feature(feature: dict, source_family: str, ingest_batch_id: str) -> LFTRWaterbody | None:
    geometry = feature.get('geometry') or {}
    if geometry.get('type') not in {'Polygon', 'MultiPolygon'} or not _coords(geometry):
        return None
    props = feature.get('properties') or {}
    name = props.get('name') or props.get('GNIS_Name') or props.get('gnis_name') or props.get('FType') or 'Unnamed inland water'
    kind = normalize_kind(str(props.get('kind') or props.get('FType') or props.get('ftype') or name))
    bbox = geometry_bbox(geometry)
    area = float(props.get('area_km2') or props.get('AreaSqKm') or area_km2_from_bbox(bbox))
    stable_id = stable_id_for(source_family, props, geometry, name, area)
    return LFTRWaterbody(stable_id=stable_id, source=source_label(source_family), source_family=source_family, source_id=str(props.get('id') or props.get('OBJECTID') or props.get('COMID') or stable_id), name=name, kind=kind, area_km2=area, geom=geometry, label_point=label_point(geometry), bbox=bbox, properties=props, ingest_batch_id=ingest_batch_id)


def normalize_geojson(payload: dict, source_family: str, ingest_batch_id: str) -> list[LFTRWaterbody]:
    features = payload.get('features', [])
    return [item for item in (normalize_feature(feature, source_family, ingest_batch_id) for feature in features) if item is not None]
