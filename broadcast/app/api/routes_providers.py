from fastapi import APIRouter, HTTPException, Query
from app.providers.gfs_ncss import get_gfs_provider
from app.providers.rtofs_ncep import get_rtofs_provider
from app.providers.catalog import provider_catalog
from app.providers.chlorophyll import chlorophyll_status
from app.services.field_truth_engine import get_field_truth_engine
from app.prerender.cache import get_render_cache
from app.spatial.viewport_query import parse_bbox
from app.services.marine_land_mask import marine_mask_for_bbox

router = APIRouter(prefix="/gfs/api", tags=["providers"])


def bbox_from_query(bbox: str):
    try:
        return parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/providers/status")
def provider_status() -> dict:
    gfs = get_gfs_provider().status()
    rtofs = get_rtofs_provider().status()
    catalog = provider_catalog()["providers"]
    return {"ok": True, "provider_mode": gfs.mode, "providers": {"gfs": {**gfs.model_dump(mode="json"), "catalog": catalog["gfs_ncss_atmosphere"]}, "rtofs": {**rtofs.model_dump(mode="json"), "catalog": catalog["rtofs_ncep_ocean"]}, "chlorophyll": {**chlorophyll_status(), "catalog": catalog["chlorophyll_ocean_color"]}}, "render_cache": get_render_cache().status()}


@router.get("/providers/catalog")
def providers_catalog() -> dict:
    return provider_catalog()


@router.get("/providers/gfs")
def provider_gfs(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat")) -> dict:
    frame, status = get_gfs_provider().fetch_atmosphere(bbox_from_query(bbox))
    return {"ok": True, "status": status.model_dump(mode="json"), "frame": frame.model_dump(mode="json")}


@router.get("/providers/rtofs")
def provider_rtofs(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat")) -> dict:
    frame, status = get_rtofs_provider().fetch_ocean(bbox_from_query(bbox))
    return {"ok": True, "status": status.model_dump(mode="json"), "frame": frame.model_dump(mode="json")}


@router.get("/marine-mask")
def marine_mask(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat")) -> dict:
    parsed = bbox_from_query(bbox)
    return {"ok": True, "bbox": parsed.model_dump(mode="json"), "marine_land_mask": marine_mask_for_bbox(parsed)}


@router.get("/field-truth")
def field_truth(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    debug_raw: bool = Query(False, description="show raw provider diagnostics instead of truth-safe stream patches"),
) -> dict:
    parsed = bbox_from_query(bbox)
    engine = get_field_truth_engine()
    if debug_raw:
        atmosphere_patch, atmosphere_status = engine.atmosphere_patch(parsed)
        ocean_patch, ocean_status = engine.ocean_patch(parsed)
    else:
        atmosphere_patch, atmosphere_status = engine.atmosphere_stream_patch(parsed)
        ocean_patch, ocean_status = engine.ocean_stream_patch(parsed)
    return {"ok": True, "debug_raw": debug_raw, "atmosphere": {"status": atmosphere_status.model_dump(mode="json") if debug_raw else atmosphere_patch.payload.get("provider"), "patch": atmosphere_patch.model_dump(mode="json")}, "ocean": {"status": ocean_status.model_dump(mode="json") if debug_raw else ocean_patch.payload.get("provider"), "patch": ocean_patch.model_dump(mode="json")}}
