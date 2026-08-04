import importlib
import importlib.util
from contextlib import contextmanager
from app.core.config import get_settings


def psycopg_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


@contextmanager
def postgis_connection():
    settings = get_settings()
    if not settings.postgis_dsn:
        raise RuntimeError("LFTR_POSTGIS_DSN is not configured")
    if not psycopg_available():
        raise RuntimeError("psycopg is not installed; install lftr-next with PostGIS extras")
    psycopg = importlib.import_module("psycopg")
    connection = psycopg.connect(settings.postgis_dsn)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def safe_postgis_status() -> dict:
    settings = get_settings()
    return {
        "enabled": settings.postgis_enabled,
        "configured": bool(settings.postgis_dsn),
        "schema": settings.postgis_schema,
        "driver_available": psycopg_available(),
    }
