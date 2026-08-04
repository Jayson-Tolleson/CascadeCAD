from app.core.config import get_settings
from app.spatial.usgs.sources import SOURCE_FAMILIES


def usgs_catalog_entry() -> dict:
    settings = get_settings()
    return {
        'provider_id': 'usgs_hydrography',
        'provider_name': 'USGS Hydrography / 3DHP / NHDPlus / NHD',
        'role': 'stable spatial truth',
        'source_families': SOURCE_FAMILIES,
        'preferred': '3dhp when configured; nhdplus_hr/nhd as legacy fallback/reference; mock for offline checks',
        'configured_source_family': settings.usgs_source_family,
        'normalized_entity': 'waterbody',
        'status': 'optional spatial ingest',
        'output': 'PostGIS waterbodies / viewport-spatial waterbodies',
        'parser_status': 'adapter_ingest_contract; source-specific fetchers are optional and cache-backed',
        'todo': ['Add production 3DHP source config', 'Add robust CRS repair/projection with geospatial deps', 'Pass #7 only stores stable inland-water geometry; live lake temperature is later'],
    }
