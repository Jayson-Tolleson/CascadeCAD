from typing import Dict, List, Tuple

from .document import Document, Part
from .adapter import CadKernelAdapter
from .exceptions import CadOperationException, CapabilityException

class Operations:
    """Encapsulates all CAD geometry modification operations."""

    def __init__(self, adapter: CadKernelAdapter):
        self.adapter = adapter

    def _check_capability(self, op_name: str):
        if self.adapter.get_name() != "CadQuery":
            raise CapabilityException(f"Operation '{op_name}' requires the CadQuery kernel.")

    # --- Primitives ---
    def create_primitive(self, primitive_type: str, params: Dict) -> Part:
        self._check_capability(f"create_{primitive_type}")
        
        if primitive_type == "box":
            dx = params.get('dx', 50.0)
            dy = params.get('dy', 50.0)
            dz = params.get('dz', 50.0)
            geom = self.adapter.create_box(dx, dy, dz)
            return Part(name="Box", geometry=geom)
        
        elif primitive_type == "cylinder":
            radius = params.get('radius', 10.0)
            height = params.get('height', 50.0)
            geom = self.adapter.create_cylinder(radius, height)
            return Part(name="Cylinder", geometry=geom)

        elif primitive_type == "sphere":
            radius = params.get('radius', 20.0)
            geom = self.adapter.create_sphere(radius)
            return Part(name="Sphere", geometry=geom)

        elif primitive_type == "cone":
            r1 = params.get('radius1', 20.0)
            r2 = params.get('radius2', 5.0)
            height = params.get('height', 40.0)
            geom = self.adapter.create_cone(r1, r2, height)
            return Part(name="Cone", geometry=geom)

        elif primitive_type == "torus":
            r1 = params.get('radius1', 20.0)
            r2 = params.get('radius2', 5.0)
            geom = self.adapter.create_torus(r1, r2)
            return Part(name="Torus", geometry=geom)
            
        else:
            raise CadOperationException(f"Unknown primitive type: {primitive_type}")

    # --- Booleans ---
    def boolean_operation(self, doc: Document, op_type: str, target_id: str, tool_ids: List[str]) -> Tuple[Part, List[str]]:
        self._check_capability(op_type)
        
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

        new_part = Part(name=f"{op_type.capitalize()}Result", geometry=result_geom)
        consumed_ids = [target_id] + tool_ids
        return new_part, consumed_ids