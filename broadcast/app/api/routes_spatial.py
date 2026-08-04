from fastapi import APIRouter, HTTPException, Query
from app.spatial.viewport_query import build_viewport_spatial, parse_bbox
from app.spatial.usgs.ingest import load_cached_mock_waterbodies

router = APIRouter(prefix="/gfs/api", tags=["spatial"])


def bbox_from_query(bbox: str):
    try:
        return parse_bbox(bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/reports")
def reports(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"), tier: str = Query("regional")) -> dict:
    parsed = bbox_from_query(bbox)
    spatial = build_viewport_spatial(parsed, tier=tier)
    rows = spatial.get("locations", spatial.get("reports", []))
    return {"ok": True, "bbox": parsed.model_dump(), "tier": tier, "reports": rows, "source": spatial.get("diagnostics", {}).get("source", spatial.get("spatial_mode")), "postgis": spatial.get("postgis", {})}


@router.get("/locations")
def locations(bbox: str = Query("-125,32,-117,38", description="minLon,minLat,maxLon,maxLat"), tier: str = Query("regional")) -> dict:
    parsed = bbox_from_query(bbox)
    spatial = build_viewport_spatial(parsed, tier=tier)
    rows = spatial.get("locations", spatial.get("reports", []))
    return {"ok": True, "bbox": parsed.model_dump(), "tier": tier, "locations": rows, "reports": rows, "source": spatial.get("diagnostics", {}).get("source", spatial.get("spatial_mode")), "postgis": spatial.get("postgis", {})}


@router.get("/viewport-spatial")
def viewport_spatial(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    tier: str = Query("regional"),
):
    return build_viewport_spatial(bbox_from_query(bbox), tier=tier)


@router.get("/waterbodies")
def waterbodies(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    tier: str = Query("regional"),
) -> dict:
    parsed = bbox_from_query(bbox)
    spatial = build_viewport_spatial(parsed, tier=tier)
    return {"ok": True, "bbox": parsed.model_dump(), "tier": tier, "waterbodies": spatial.get("waterbodies", load_cached_mock_waterbodies(parsed, tier=tier)), "source": spatial.get("diagnostics", {}).get("source", spatial.get("spatial_mode"))}
