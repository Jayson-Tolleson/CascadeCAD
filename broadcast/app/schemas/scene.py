from typing import Any, Literal
from pydantic import BaseModel, Field


class BBox(BaseModel):
    west: float
    south: float
    east: float
    north: float


class Viewport(BaseModel):
    latitude: float
    longitude: float
    altitude_m: float = Field(alias="altitudeM")
    heading: float
    tilt: float


class SceneLayer(BaseModel):
    id: str
    label: str
    enabled: bool = True
    kind: Literal["field", "scalar_field", "entity", "spatial", "event", "spatial_points", "report"]


class SceneSnapshot(BaseModel):
    ok: bool
    scene_id: str
    generated_at: str
    bbox: BBox
    viewport: Viewport
    layers: list[SceneLayer]
    spatial: dict[str, Any]
    fields: dict[str, Any]
