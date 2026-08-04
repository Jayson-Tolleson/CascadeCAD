from app.core.config import get_settings
from app.db.connect import safe_postgis_status


def usgs_status(last_ingest: dict | None = None) -> dict:
    settings = get_settings()
    return {
        'enabled': settings.usgs_enabled,
        'source_family': settings.usgs_source_family,
        'cache_dir': settings.usgs_cache_dir,
        'max_features': settings.usgs_max_features,
        'default_bbox': settings.usgs_default_bbox,
        'postgis': safe_postgis_status(),
        'last_ingest': last_ingest,
        'secrets_exposed': False,
    }
