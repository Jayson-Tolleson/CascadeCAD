from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import base64
from io import BytesIO

# --- Capability-based Imports ---
try:
    import cadquery as cq
    from cadquery.occ_impl.shapes import Shape, Compound
    from cadquery.importers import importStep, importIges
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    # Define dummy classes for type hinting if CadQuery is not available
    class Shape: pass
    class Compound: pass

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False


class CadKernelAdapter(ABC):
    """Abstract Base Class for a CAD Kernel Adapter."""

    @abstractmethod
    def get_name(self) -> str:
        pass

    # --- Primitives ---
    @abstractmethod
    def create_box(self, dx: float, dy: float, dz: float) -> Any:
        pass

    @abstractmethod
    def create_cylinder(self, radius: float, height: float) -> Any:
        pass

    @abstractmethod
    def create_sphere(self, radius: float) -> Any:
        pass

    @abstractmethod
    def create_cone(self, radius1: float, radius2: float, height: float) -> Any:
        pass

    @abstractmethod
    def create_torus(self, radius1: float, radius2: float) -> Any:
        pass

    # --- Booleans ---
    @abstractmethod
    def fuse(self, main_obj: Any, tool_objs: List[Any]) -> Any:
        pass

    @abstractmethod
    def cut(self, main_obj: Any, tool_objs: List[Any]) -> Any:
        pass

    @abstractmethod
    def intersect(self, main_obj: Any, tool_objs: List[Any]) -> Any:
        pass

    # --- Tessellation ---
    @abstractmethod
    def tessellate(self, obj: Any, tolerance: float = 0.1, angular_tolerance: float = 0.1) -> Dict[str, Any]:
        pass

    # --- Import/Export ---
    @abstractmethod
    def import_step(self, file_path: str) -> List[Any]:
        pass

    @abstractmethod
    def import_iges(self, file_path: str) -> List[Any]:
        pass

    @abstractmethod
    def export_step(self, objs: List[Any], file_path: str) -> bool:
        pass

    @abstractmethod
    def export_iges(self, objs: List[Any], file_path: str) -> bool:
        pass

    @abstractmethod
    def export_stl(self, objs: List[Any], file_path: str, tolerance: float = 0.1) -> bool:
        pass
    
    # --- B-Rep Serialization ---
    @abstractmethod
    def shape_to_brep_string(self, obj: Any) -> Optional[str]:
        pass

    @abstractmethod
    def brep_string_to_shape(self, brep_string: str) -> Optional[Any]:
        pass


class NoCadAdapter(CadKernelAdapter):
    """A fallback adapter for when no CAD kernel is installed."""
    def get_name(self) -> str:
        return "None"

    def _not_implemented(self, *args, **kwargs):
        raise NotImplementedError("A required CAD library (like CadQuery) is not installed.")

    create_box = _not_implemented
    create_cylinder = _not_implemented
    create_sphere = _not_implemented
    create_cone = _not_implemented
    create_torus = _not_implemented
    fuse = _not_implemented
    cut = _not_implemented
    intersect = _not_implemented
    tessellate = _not_implemented
    import_step = _not_implemented
    import_iges = _not_implemented
    export_step = _not_implemented
    export_iges = _not_implemented
    export_stl = _not_implemented
    shape_to_brep_string = _not_implemented
    brep_string_to_shape = _not_implemented


class CadQueryAdapter(CadKernelAdapter):
    """Adapter for the CadQuery/OpenCASCADE kernel."""
    def get_name(self) -> str:
        return "CadQuery"

    def _get_solid(self, obj: Any) -> Optional[Shape]:
        if isinstance(obj, cq.Workplane):
            # Handle cases where the workplane might be empty or contain non-solids
            solids = obj.solids().vals()
            return solids[0] if solids else None
        if isinstance(obj, (Shape, Compound)):
            return obj
        return None

    def create_box(self, dx: float, dy: float, dz: float) -> cq.Workplane:
        return cq.Workplane("XY").box(dx, dy, dz)

    def create_cylinder(self, radius: float, height: float) -> cq.Workplane:
        return cq.Workplane("XY").cylinder(height, radius)

    def create_sphere(self, radius: float) -> cq.Workplane:
        return cq.Workplane("XY").sphere(radius)

    def create_cone(self, radius1: float, radius2: float, height: float) -> cq.Workplane:
        return cq.Workplane("XY").cone(height, radius1, radius2)

    def create_torus(self, radius1: float, radius2: float) -> cq.Workplane:
        return cq.Workplane("XY").torus(radius1, radius2)

    def fuse(self, main_obj: Any, tool_objs: List[Any]) -> cq.Workplane:
        main_solid = self._get_solid(main_obj)
        if not main_solid:
            raise ValueError("Main object for fuse is not a valid solid.")
        
        wp = cq.Workplane(main_solid)
        for tool in tool_objs:
            tool_solid = self._get_solid(tool)
            if tool_solid:
                wp = wp.union(tool_solid)
        return wp

    def cut(self, main_obj: Any, tool_objs: List[Any]) -> cq.Workplane:
        main_solid = self._get_solid(main_obj)
        if not main_solid:
            raise ValueError("Main object for cut is not a valid solid.")

        wp = cq.Workplane(main_solid)
        for tool in tool_objs:
            tool_solid = self._get_solid(tool)
            if tool_solid:
                wp = wp.cut(tool_solid)
        return wp

    def intersect(self, main_obj: Any, tool_objs: List[Any]) -> cq.Workplane:
        main_solid = self._get_solid(main_obj)
        if not main_solid:
            raise ValueError("Main object for intersect is not a valid solid.")

        wp = cq.Workplane(main_solid)
        for tool in tool_objs:
            tool_solid = self._get_solid(tool)
            if tool_solid:
                wp = wp.intersect(tool_solid)
        return wp

    def tessellate(self, obj: Any, tolerance: float = 0.1, angular_tolerance: float = 0.1) -> Dict[str, Any]:
        solid = self._get_solid(obj)
        if not solid:
            return {'vertices': [], 'indices': [], 'normals': []}

        # Use OCCT's triangulation
        triangulation = solid.tessellate(tolerance=tolerance, angularTolerance=angular_tolerance)
        
        vertices = [v for p in triangulation[0] for v in (p.x, p.y, p.z)]
        indices = [i for f in triangulation[1] for i in f]
        
        # Normals can be calculated from the triangulation
        normals = [n for p in triangulation[0] for n in solid.getNormal(p).toTuple()] if triangulation[0] else []

        return {'vertices': vertices, 'indices': indices, 'normals': normals}

    def import_step(self, file_path: str) -> List[Any]:
        result = importStep(file_path)
        if isinstance(result, Compound):
            return list(result.Solids())
        return [result]

    def import_iges(self, file_path: str) -> List[Any]:
        result = importIges(file_path)
        if isinstance(result, Compound):
            return list(result.Solids())
        return [result]

    def export_step(self, objs: List[Any], file_path: str) -> bool:
        solids = [self._get_solid(o) for o in objs if self._get_solid(o)]
        if not solids: return False
        compound = cq.Compound.makeCompound(solids)
        cq.exporters.export(compound, file_path, 'STEP')
        return True

    def export_iges(self, objs: List[Any], file_path: str) -> bool:
        solids = [self._get_solid(o) for o in objs if self._get_solid(o)]
        if not solids: return False
        compound = cq.Compound.makeCompound(solids)
        cq.exporters.export(compound, file_path, 'IGES')
        return True

    def export_stl(self, objs: List[Any], file_path: str, tolerance: float = 0.1) -> bool:
        solids = [self._get_solid(o) for o in objs if self._get_solid(o)]
        if not solids: return False
        compound = cq.Compound.makeCompound(solids)
        cq.exporters.export(compound, file_path, 'STL', tolerance=tolerance)
        return True

    def shape_to_brep_string(self, obj: Any) -> Optional[str]:
        solid = self._get_solid(obj)
        if not solid: return None
        
        bio = BytesIO()
        solid.exportBrep(bio)
        bio.seek(0)
        brep_bytes = bio.read()
        return base64.b64encode(brep_bytes).decode('utf-8')

    def brep_string_to_shape(self, brep_string: str) -> Optional[Any]:
        brep_bytes = base64.b64decode(brep_string)
        bio = BytesIO(brep_bytes)
        
        shape = Shape.importBrep(bio)

        if shape.val().IsNull():
            return None
        
        return shape


def get_adapter() -> CadKernelAdapter:
    """Factory function to get the best available CAD adapter."""
    if CADQUERY_AVAILABLE:
        return CadQueryAdapter()
    return NoCadAdapter()