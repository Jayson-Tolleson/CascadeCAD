from datetime import datetime, timezone
from app.services.viewport import default_viewport
from app.fields.tiles import default_field_bbox
from app.providers.gfs_ncss import get_gfs_provider
from app.providers.rtofs_ncep import get_rtofs_provider
from app.layers.compiler import layer_status


LAYER_CONTRACTS = [
    {"id": "locations", "label": "Locations", "kind": "spatial_points", "enabled": True},
    {"id": "clouds", "label": "Clouds", "kind": "field", "enabled": True},
    {"id": "rain", "label": "Rain", "kind": "field", "enabled": True},
    {"id": "bait", "label": "Bait", "kind": "field", "enabled": True},
    {"id": "boats", "label": "Boats", "kind": "entity", "enabled": True},
    {"id": "shark-intel", "label": "Shark Intel", "kind": "event", "enabled": True},
    {"id": "inland-water", "label": "Inland Water", "kind": "field", "enabled": True},
    {"id": "lightning", "label": "Lightning", "kind": "report", "enabled": False},
]


def _scene_provider_summary(status, realtime_ok: bool) -> dict:
    return {
        "provider": status.provider,
        "mode": status.mode,
        "enabled": status.enabled,
        "live_ok": bool(status.live_ok and realtime_ok),
        "cache_hit": bool(status.cache_hit),
        "realtime_ok": bool(realtime_ok),
        "valid_time": status.valid_time,
        "generated_time": status.generated_time,
        "diagnostics": "raw provider details available at /gfs/api/providers/status",
    }


def build_scene_snapshot() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    _, gfs_status = get_gfs_provider().fetch_atmosphere(default_field_bbox())
    _, rtofs_status = get_rtofs_provider().fetch_ocean(default_field_bbox())
    atmosphere_source = _scene_provider_summary(gfs_status, realtime_ok=gfs_status.live_ok and not gfs_status.degraded)
    ocean_source = _scene_provider_summary(rtofs_status, realtime_ok=rtofs_status.live_ok and not rtofs_status.degraded)
    compiled_layers = layer_status()
    return {
        "ok": True,
        "scene_id": f"scene-{now}",
        "generated_at": now,
        "bbox": {"west": -125.0, "south": 32.0, "east": -117.0, "north": 38.0},
        "viewport": default_viewport(),
        "layers": compiled_layers["layers"],
        "spatial": {
            "projection": "WGS84",
            "postgis": {"status": "optional", "contract": "place-aware spatial queries when configured"},
            "objects": [],
        },
        "route_contract_version": "lftr.scene.v1",
        "renderer": {"budgets": compiled_layers["layers"], "expectations": compiled_layers["renderer_expectations"]},
        "provider_status": compiled_layers["providers"],
        "spatial_status": compiled_layers["spatial"],
        "fields": {
            "clouds": {"status": "provider_live_or_no_data", "patch_count": 1, "atmosphere_provider": atmosphere_source},
            "rain": {"status": "provider_live_or_no_data", "patch_count": 1, "atmosphere_provider": atmosphere_source},
            "ocean": {"status": "provider_live_or_no_data", "patch_count": 1, "ocean_provider": ocean_source},
            "atmosphere_provider": atmosphere_source,
            "ocean_provider": ocean_source,
        },
    }


# Backward compatibility for old checks/imports.
def build_mock_scene_snapshot() -> dict:
    return build_scene_snapshot()
