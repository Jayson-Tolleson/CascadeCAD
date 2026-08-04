from pathlib import Path
from app.core.config import get_settings
from app.schemas.scene import BBox
from app.spatial.base import SpatialFeature
from app.spatial.csv_reports import filter_reports_by_bbox, load_reports
from app.spatial.postgis_optional import postgis_status
from app.spatial.usgs.ingest import load_cached_mock_waterbodies
from app.services.marine_land_mask import marine_mask_for_point


def parse_bbox(value: str) -> BBox:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
    return BBox(west=parts[0], south=parts[1], east=parts[2], north=parts[3])


def reports_csv_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    fish_locations = root / "data" / "fishloclist.csv"
    if fish_locations.exists():
        return fish_locations
    return root / "data" / "reports.csv"


def bbox_intersects(bbox: BBox, west: float, south: float, east: float, north: float) -> bool:
    return not (bbox.east < west or bbox.west > east or bbox.north < south or bbox.south > north)


def bbox_center(bbox: BBox) -> tuple[float, float]:
    return ((bbox.south + bbox.north) / 2, (bbox.west + bbox.east) / 2)


def _with_marine_mask(report):
    if not getattr(report, "marine_mask", None):
        report.marine_mask = marine_mask_for_point(report.longitude, report.latitude)
    return report


def query_reports(bbox: BBox):
    csv_reports = [_with_marine_mask(report) for report in filter_reports_by_bbox(load_reports(reports_csv_path()), bbox)]
    if csv_reports:
        return csv_reports
    if bbox_intersects(bbox, -125.0, 32.0, -117.0, 38.0):
        from app.spatial.base import ReportPoint
        return [_with_marine_mask(ReportPoint(id="mock_report_socal_001", title="Mock Southern California report", latitude=33.72, longitude=-118.24, observed_at="mock", summary="mock_spatial report near LA/Long Beach", source="mock_spatial"))]
    return []


def mock_lakes(bbox: BBox) -> list[SpatialFeature]:
    if bbox_intersects(bbox, -83.5, 24.0, -79.0, 28.8):
        return [SpatialFeature(id="lake-okeechobee", kind="lake", label="Mock Lake Okeechobee", latitude=26.94, longitude=-80.80, metadata={"source": "mock_spatial"})]
    if bbox_intersects(bbox, -125.0, 32.0, -117.0, 38.0):
        return [SpatialFeature(id="mock_lake_socal_001", kind="lake", label="Mock SoCal lake", latitude=34.10, longitude=-117.20, metadata={"source": "mock_spatial"})]
    lat, lon = bbox_center(bbox)
    return [SpatialFeature(id="mock_generic_waterbody_001", kind="waterbody", label="Generic mock waterbody", latitude=lat, longitude=lon, metadata={"source": "mock_spatial", "generic": True})]


def mock_harbors(bbox: BBox) -> list[SpatialFeature]:
    if bbox_intersects(bbox, -83.5, 24.0, -79.0, 28.8):
        return [
            SpatialFeature(id="harbor-port-everglades", kind="harbor", label="Mock Port Everglades", latitude=26.091, longitude=-80.116, metadata={"source": "mock_spatial"}),
            SpatialFeature(id="harbor-miami", kind="harbor", label="Mock PortMiami", latitude=25.778, longitude=-80.170, metadata={"source": "mock_spatial"}),
        ]
    if bbox_intersects(bbox, -125.0, 32.0, -117.0, 38.0):
        return [SpatialFeature(id="mock_harbor_la_long_beach", kind="harbor", label="Mock LA/Long Beach Harbor", latitude=33.754, longitude=-118.216, metadata={"source": "mock_spatial"})]
    return []


def _postgis_response(bbox: BBox, tier: str):
    from app.spatial.postgis_repository import PostGISSpatialRepository
    repo = PostGISSpatialRepository()
    if not repo.available():
        return None
    try:
        reports = repo.query_reports(bbox)
        waterbodies = repo.query_waterbodies(bbox, tier)
        harbors = repo.query_harbors(bbox)
        coast_mask = repo.query_coast_mask(bbox, tier) or {"id": f"coast-mask-{tier}", "status": "postgis-empty"}
        status = repo.status()
        return {"ok": True, "bbox": bbox.model_dump(), "tier": tier, "geometry_tier": tier, "spatial_mode": "postgis", "reports": reports, "lakes": waterbodies, "waterbodies": waterbodies, "harbors": harbors, "coast_mask": coast_mask, "postgis": {k: v for k, v in status.items() if k != "dsn"}, "diagnostics": {"source": "postgis", "fallback": False}}
    except Exception as exc:
        if get_settings().spatial_mode == "postgis":
            raise
        return {"error": str(exc)}


def build_viewport_spatial(bbox: BBox, tier: str = "regional"):
    settings = get_settings()
    if settings.spatial_mode in {"postgis", "hybrid"}:
        postgis_payload = _postgis_response(bbox, tier)
        if postgis_payload and "error" not in postgis_payload:
            return postgis_payload
    status = postgis_status(settings.postgis_enabled, settings.postgis_dsn)
    waterbodies = load_cached_mock_waterbodies(bbox, tier=tier)
    lakes = [item for item in waterbodies if item.get("kind") in {"lake", "reservoir", "pond", "unknown_waterbody"}]
    harbors = mock_harbors(bbox)
    return {"ok": True, "bbox": bbox.model_dump(), "tier": tier, "geometry_tier": tier, "spatial_mode": "mock" if settings.spatial_mode != "postgis" else "mock-fallback", "reports": [report.model_dump() for report in query_reports(bbox)], "lakes": lakes, "waterbodies": waterbodies, "harbors": [harbor.model_dump() for harbor in harbors], "coast_mask": {"id": f"coast-mask-{tier}", "status": "mock_spatial", "bbox": bbox.model_dump()}, "postgis": status, "diagnostics": {"source": "mock_spatial", "fallback": True, "usgs": "mock_or_cache"}}
