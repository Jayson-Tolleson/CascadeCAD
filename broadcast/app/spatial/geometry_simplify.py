from app.core.config import get_settings


def simplify_tolerance(tier: str) -> float:
    settings = get_settings()
    if tier == "global":
        return settings.geometry_simplify_global
    if tier == "local":
        return settings.geometry_simplify_local
    return settings.geometry_simplify_regional
