from typing import Any, Literal
from pydantic import BaseModel, Field
from app.schemas.scene import BBox


class AtmosphereFieldFrame(BaseModel):
    bbox: BBox
    valid_time: str
    grid_shape: tuple[int, int]
    levels: list[str]
    channels: dict[str, list[list[float]]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class OceanFieldFrame(BaseModel):
    bbox: BBox
    valid_time: str
    grid_shape: tuple[int, int]
    depth_levels: list[str]
    channels: dict[str, list[list[float]]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class FieldPatch(BaseModel):
    patch_id: str
    field_type: Literal["atmosphere", "ocean"]
    tile_id: str
    bbox: BBox
    lod: int
    channels: list[str]
    encoding: Literal["json-grid"] = "json-grid"
    payload: dict[str, Any]
