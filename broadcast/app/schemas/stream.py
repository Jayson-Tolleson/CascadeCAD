from typing import Any
from pydantic import BaseModel


class StreamEvent(BaseModel):
    event: str
    id: str
    data: dict[str, Any]
