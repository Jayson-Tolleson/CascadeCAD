from fastapi import APIRouter, HTTPException, Query

from app.prerender.cache import get_render_cache
from app.prerender.worker import precompute_viewport_render_features, precompute_cloud_render_features
from app.spatial.viewport_query import parse_bbox

router = APIRouter(prefix="/gfs/api/prerender", tags=["prerender"])


def bbox_from_query(bbox: str):
    try:
        return parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/status")
def prerender_status() -> dict:
    return {"ok": True, "render_cache": get_render_cache().status()}


@router.post("/viewport")
def prerender_viewport(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    tier: str = Query("regional"),
) -> dict:
    return precompute_viewport_render_features(bbox_from_query(bbox), tier=tier)


@router.post("/clouds")
def prerender_clouds(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    tier: str = Query("regional"),
) -> dict:
    return precompute_cloud_render_features(bbox_from_query(bbox), tier=tier)
