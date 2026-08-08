import uuid
from typing import Dict, Any, Optional, List

class Part:
    """Represents a single geometric object in the document."""
    def __init__(self, name: str, geometry: Any, part_id: Optional[str] = None):
        self.id = part_id or str(uuid.uuid4())
        self.name = name
        self.geometry = geometry  # This is the CAD kernel object (e.g., cq.Workplane)
        self.transform = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1] # Identity matrix (placeholder)
        self.visible = True
        self.display_properties = {"color": [0.8, 0.8, 0.8], "opacity": 1.0}
        self.tessellation_cache: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes part metadata to a dictionary (without geometry)."""
        return {
            "id": self.id,
            "name": self.name,
            "transform": self.transform,
            "visible": self.visible,
            "display_properties": self.display_properties,
        }

class Document:
    """Represents the entire CAD document state."""
    def __init__(self):
        self.xbf_version = "1.0"
        self.units = "mm"
        self.parts: Dict[str, Part] = {}
        self.metadata: Dict[str, Any] = {}

    def add_part(self, part: Part):
        """Adds a part to the document."""
        self.parts[part.id] = part

    def remove_part(self, part_id: str):
        """Removes a part from the document."""
        if part_id in self.parts:
            del self.parts[part_id]

    def get_part(self, part_id: str) -> Optional[Part]:
        """Retrieves a part by its ID."""
        return self.parts.get(part_id)

    def get_all_parts(self) -> List[Part]:
        """Returns a list of all parts in the document."""
        return list(self.parts.values())

    def clear(self):
        """Clears all parts and resets the document."""
        self.parts.clear()
        self.metadata.clear()
        self.units = "mm"

    def get_selected_parts(self, selection_ids: List[str]) -> List[Part]:
        """Returns a list of Part objects based on a list of IDs."""
        return [part for part_id, part in self.parts.items() if part_id in selection_ids]