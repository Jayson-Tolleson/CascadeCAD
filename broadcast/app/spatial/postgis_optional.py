from app.core.config import get_settings
from app.db.connect import safe_postgis_status


def postgis_status(enabled: bool | None = None, dsn: str | None = None) -> dict:
    settings = get_settings()
    status = safe_postgis_status()
    status.update({
        "enabled": settings.postgis_enabled if enabled is None else enabled,
        "configured": bool(settings.postgis_dsn if dsn is None else dsn),
        "spatial_mode": settings.spatial_mode,
        "status": "available" if status["driver_available"] and status["configured"] else "unavailable",
    })
    return status
