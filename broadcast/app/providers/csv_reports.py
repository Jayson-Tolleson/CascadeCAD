from app.schemas.scene import BBox
from app.spatial.viewport_query import query_reports


def reports_for_bbox(bbox: BBox):
    return query_reports(bbox)
