from typing import Dict, Any

from .document import Part
from .adapter import CadKernelAdapter
from .exceptions import CadOperationException

class Tessellator:
    """Handles the generation of mesh data from B-Rep models."""

    def __init__(self, adapter: CadKernelAdapter):
        self.adapter = adapter
        self.tolerance = 0.1
        self.angular_tolerance = 0.2

    def tessellate_part(self, part: Part) -> Dict[str, Any]:
        """
        Tessellates a single Part object.
        Returns a dictionary containing vertices, faces, and normals.
        """
        if not part.geometry:
            return {'vertices': [], 'faces': [], 'normals': []}

        try:
            mesh_data = self.adapter.tessellate(
                part.geometry,
                tolerance=self.tolerance,
                angular_tolerance=self.angular_tolerance
            )
            return mesh_data
        except Exception as e:
            raise CadOperationException(f"Failed to tessellate part {part.name}: {e}")