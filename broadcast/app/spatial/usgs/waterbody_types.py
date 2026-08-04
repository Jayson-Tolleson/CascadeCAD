from typing import Any, Literal
from pydantic import BaseModel, Field

WaterbodyKind = Literal['lake', 'reservoir', 'pond', 'river', 'canal', 'wetland', 'bay', 'unknown_waterbody']


class LFTRWaterbody(BaseModel):
    stable_id: str
    source: str
    source_family: str
    source_id: str | None = None
    name: str
    kind: WaterbodyKind = 'unknown_waterbody'
    area_km2: float = 0
    geom: dict[str, Any]
    label_point: dict[str, float]
    bbox: list[float]
    properties: dict[str, Any] = Field(default_factory=dict)
    ingest_batch_id: str

    def viewport_dict(self, include_geometry: bool = True) -> dict[str, Any]:
        payload = {
            'id': self.stable_id,
            'stable_id': self.stable_id,
            'name': self.name,
            'kind': self.kind,
            'source': self.source,
            'source_family': self.source_family,
            'source_id': self.source_id,
            'area_km2': self.area_km2,
            'label_point': self.label_point,
            'bbox': self.bbox,
            'properties': self.properties,
        }
        if include_geometry:
            payload['geometry'] = self.geom
        return payload
