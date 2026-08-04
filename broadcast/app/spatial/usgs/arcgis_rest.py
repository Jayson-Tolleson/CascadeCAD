import json
import urllib.parse
import urllib.request
from app.core.config import get_settings
from app.schemas.scene import BBox


def query_arcgis_geojson(bbox: BBox) -> dict:
    settings = get_settings()
    if not settings.usgs_arcgis_url:
        raise RuntimeError('LFTR_USGS_ARCGIS_URL is not configured')
    layer = f'/{settings.usgs_arcgis_layer}' if settings.usgs_arcgis_layer else ''
    base = settings.usgs_arcgis_url.rstrip('/') + layer + '/query'
    params = {
        'f': 'geojson',
        'where': '1=1',
        'outFields': '*',
        'geometry': f'{bbox.west},{bbox.south},{bbox.east},{bbox.north}',
        'geometryType': 'esriGeometryEnvelope',
        'inSR': '4326',
        'outSR': '4326',
        'returnGeometry': 'true',
        'resultRecordCount': str(settings.usgs_max_features),
    }
    with urllib.request.urlopen(f'{base}?{urllib.parse.urlencode(params)}', timeout=settings.usgs_timeout_seconds) as response:
        return json.loads(response.read().decode('utf-8'))
