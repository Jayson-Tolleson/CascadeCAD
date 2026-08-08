from typing import Dict, List, Tuple

from .document import Document, Part
from .adapter import CadKernelAdapter
from .exceptions import CadOperationException, CapabilityException

class Operations:
    """Encapsulates all CAD geometry modification operations."""

    def __init__(self, adapter: CadKernelAdapter):
        self.adapter = adapter

    def _check_capability(self, is_available: bool, op_name: str):
        if not is_available:
            raise CapabilityException(f"Operation '{op_name}' is not available due to missing libraries.")

    # --- Primitives ---
    def create_box(self, params: Dict) -> Part:
        self._check_capability(self.adapter.get_name() == "CadQuery", "create_box")
        dx = params.get('dx', 10.0)
        dy = params.get('dy', 10.0)
        dz = params.get('dz', 10.0)
        geom = self.adapter.create_box(dx, dy, dz)
        return Part(name="Box", geometry=geom)

    def create_cylinder(self, params: Dict) -> Part:
        self._check_capability(self.adapter.get_name() == "CadQuery", "create_cylinder")
        radius = params.get('radius', 5.0)
        height = params.get('height', 20.0)
        geom = self.adapter.create_cylinder(radius, height)
        return Part(name="Cylinder", geometry=geom)

    def create_sphere(self, params: Dict) -> Part:
        self._check_capability(self.adapter.get_name() == "CadQuery", "create_sphere")
        radius = params.get('radius', 10.0)
        geom = self.adapter.create_sphere(radius)
        return Part(name="Sphere", geometry=geom)

    # --- Booleans ---
    def boolean_operation(self, doc: Document, op_type: str, target_id: str, tool_ids: List[str]) -> Tuple[Part, List[str]]:
        self._check_capability(self.adapter.get_name() == "CadQuery", op_type)
        
        target_part = doc.get_part(target_id)
        tool_parts = [doc.get_part(tid) for tid in tool_ids]

        if not target_part or not all(tool_parts):
            raise CadOperationException("One or more objects for boolean operation not found.")

        main_obj = target_part.geometry
        tool_objs = [p.geometry for p in tool_parts]

        if op_type == "fuse":
            result_geom = self.adapter.fuse(main_obj, tool_objs)
        elif op_type == "cut":
            result_geom = self.adapter.cut(main_obj, tool_objs)
        elif op_type == "intersect":
            result_geom = self.adapter.intersect(main_obj, tool_objs)
        else:
            raise CadOperationException(f"Unknown boolean operation: {op_type}")

        new_part = Part(name=f"BooleanResult", geometry=result_geom)
        consumed_ids = [target_id] + tool_ids
        return new_part, consumed_ids

    # --- Transforms ---
    def transform_operation(self, doc: Document, op_type: str, params: Dict, selection: List[str]) -> List[str]:
        self._check_capability(self.adapter.get_name() == "CadQuery", op_type)
        
        parts_to_transform = doc.get_selected_parts(selection)
        if not parts_to_transform:
            raise CadOperationException("No valid parts selected for transform.")

        for part in parts_to_transform:
            if op_type == "translate":
                vector = params.get('vector', [0,0,0])
                part.geometry = self.adapter.translate(part.geometry, tuple(vector))
            elif op_type == "rotate":
                axis = params.get('axis', [0,0,1])
                angle = params.get('angle', 90.0)
                part.geometry = self.adapter.rotate(part.geometry, tuple(axis), angle)
            elif op_type == "scale":
                factor = params.get('factor', 1.5)
                part.geometry = self.adapter.scale(part.geometry, factor)
            else:
                raise CadOperationException(f"Unknown transform operation: {op_type}")
            
            # Invalidate tessellation cache after modification
            part.tessellation_cache = None
        
        return [part.id for part in parts_to_transform]