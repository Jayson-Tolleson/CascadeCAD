from typing import Literal
from pydantic import BaseModel, Field

LayerKind = Literal['field', 'scalar_field', 'entity', 'spatial', 'event', 'spatial_points']


class LayerContract(BaseModel):
    id: str
    label: str
    kind: LayerKind
    enabled: bool = True
    source: str
    status: str = 'ready'
    depends_on: list[str] = Field(default_factory=list)
    stream_events: list[str] = Field(default_factory=list)
    renderer: str
    budget: dict[str, int]
    degraded: bool = False
    todo: list[str] = Field(default_factory=list)
