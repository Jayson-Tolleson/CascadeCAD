from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.scene import BBox


class ReportPoint(BaseModel):
    id: str
    kind: Literal["report"] = "report"
    title: str
    latitude: float
    longitude: float
    observed_at: str
    summary: str
    source: str = "csv"
    csv_fields: dict[str, str] = Field(default_factory=dict)
    report_indices: list[str] = Field(default_factory=list)
    marine_mask: dict = Field(default_factory=dict)


class SpatialFeature(BaseModel):
    id: str
    kind: str
    label: str
    latitude: float | None = None
    longitude: float | None = None
    metadata: dict = {}


class ViewportSpatialResponse(BaseModel):
    ok: bool
    bbox: BBox
    tier: str
    reports: list[ReportPoint]
    lakes: list[SpatialFeature]
    harbors: list[SpatialFeature]
    coast_mask: dict
    postgis: dict
