from typing import Dict, Any, List
from .adapter import CADQUERY_AVAILABLE, TRIMESH_AVAILABLE

class Capabilities:
    """
    Detects and reports the available capabilities of the CAD engine
    based on installed libraries.
    """
    def __init__(self):
        self.cad_kernel_name = "CadQuery" if CADQUERY_AVAILABLE else "None"
        self.mesh_kernel_name = "Trimesh" if TRIMESH_AVAILABLE else "None"

    def get_all(self) -> Dict[str, Any]:
        """Returns a dictionary of all capabilities."""
        return {
            "kernels": self._get_kernel_caps(),
            "import_formats": self._get_import_caps(),
            "export_formats": self._get_export_caps(),
            "primitives": self._get_primitive_caps(),
            "operations": self._get_operation_caps(),
        }

    def _get_kernel_caps(self) -> Dict[str, str]:
        return {
            "brep_kernel": self.cad_kernel_name,
            "mesh_kernel": self.mesh_kernel_name,
        }

    def _get_import_caps(self) -> List[str]:
        formats = ["xbf"] # Native format is always supported
        if CADQUERY_AVAILABLE:
            formats.extend(["step", "stp", "iges", "igs"])
        if TRIMESH_AVAILABLE:
            # Trimesh supports many, but we list the most common
            formats.extend(["stl", "obj", "3mf", "ply", "gltf", "glb"])
        return sorted(list(set(formats)))

    def _get_export_caps(self) -> List[str]:
        formats = ["xbf"]
        if CADQUERY_AVAILABLE:
            formats.extend(["step", "stp", "iges", "igs", "stl"])
        if TRIMESH_AVAILABLE:
            formats.extend(["3mf", "obj", "ply", "gltf", "glb"])
        return sorted(list(set(formats)))

    def _get_primitive_caps(self) -> List[str]:
        if CADQUERY_AVAILABLE:
            return ["box", "cylinder", "sphere", "cone", "torus"]
        return []

    def _get_operation_caps(self) -> Dict[str, bool]:
        return {
            "translate": CADQUERY_AVAILABLE,
            "rotate": CADQUERY_AVAILABLE,
            "scale": CADQUERY_AVAILABLE,
            "fuse": CADQUERY_AVAILABLE,
            "cut": CADQUERY_AVAILABLE,
            "intersect": CADQUERY_AVAILABLE,
            "fillet": False, # Not implemented in this pass
            "chamfer": False, # Not implemented in this pass
            "extrude": False, # Not implemented in this pass
            "revolve": False, # Not implemented in this pass
        }