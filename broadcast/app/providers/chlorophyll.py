from app.core.config import get_settings


def chlorophyll_status() -> dict:
    settings = get_settings()
    return {
        "provider_id": "chlorophyll_ocean_color",
        "enabled": settings.chl_enabled,
        "provider": settings.chl_provider,
        "parser_status": "disabled_future_adapter",
        "live_status": "disabled",
        "degraded": True,
    }
