from typing import Dict, Any, List, Optional

from .document import Document, Part
from .adapter import get_adapter
from .capabilities import Capabilities
from .io_system import IoSystem
from .operations import Operations
from .tessellator import Tessellator
from .exceptions import CadOperationException, CapabilityException

class Engine:
    """
    The main facade for the MagicXBF CAD Engine.
    It holds the current document state and dispatches operations.
    """
    def __init__(self):
        self.adapter = get_adapter()
        self.capabilities = Capabilities()
        self.io = IoSystem(self.adapter, self.capabilities)
        self.ops = Operations(self.adapter)
        self.tessellator = Tessellator(self.adapter)
        self.document = Document()

    def _create_response(self, status: str, message: str, data: Optional[Dict] = None, object_ids: Optional[List[str]] = None) -> Dict:
        return {
            "status": status,
            "message": message,
            "data": data or {},
            "object_ids": object_ids or []
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """Returns the engine's capabilities."""
        return self.capabilities.get_all()

    def new_document(self):
        """Creates a new, empty document."""
        self.document = Document()

    def import_file(self, file_path: str, original_filename: str) -> Dict:
        """Imports a file, replacing the current document."""
        try:
            new_doc = self.io.import_file(file_path, original_filename)
            self.document = new_doc
            # Invalidate tessellation cache for all new parts
            for part in self.document.get_all_parts():
                part.tessellation_cache = None
            return self._create_response(
                "success",
                f"Successfully imported {original_filename}. Found {len(new_doc.parts)} parts.",
                object_ids=list(new_doc.parts.keys())
            )
        except (CadOperationException, CapabilityException, Exception) as e:
            return self._create_response("error", f"Import failed: {str(e)}")

    def export_file(self, file_format: str) -> Dict:
        """Exports the current document to a file."""
        try:
            if not self.document.parts:
                return self._create_response("error", "Cannot export an empty document.")
            
            result = self.io.export_file(self.document, file_format)
            return self._create_response("success", "Export successful.", data=result)
        except (CadOperationException, CapabilityException, Exception) as e:
            return self._create_response("error", f"Export failed: {str(e)}")

    def get_tessellation(self) -> Dict[str, Any]:
        """Tessellates all parts in the document for viewport rendering."""
        all_geometries = []
        for part in self.document.get_all_parts():
            if not part.visible:
                continue
            
            if part.tessellation_cache is None:
                # If cache is empty, tessellate and store
                part.tessellation_cache = self.tessellator.tessellate_part(part)

            if part.tessellation_cache and part.tessellation_cache.get('vertices'):
                geom_data = {
                    "uuid": part.id,
                    "name": part.name,
                    "vertices": part.tessellation_cache['vertices'],
                    "faces": part.tessellation_cache['faces'],
                    "normals": part.tessellation_cache['normals'],
                    "color": part.display_properties.get('color', [0.8, 0.8, 0.8]),
                    "opacity": part.display_properties.get('opacity', 1.0)
                }
                all_geometries.append(geom_data)
        
        return {"geometries": all_geometries}

    def execute_command(self, command: str, params: Dict, selection: List[str]) -> Dict:
        """Executes a generic CAD command."""
        try:
            # --- Primitive Creation ---
            if command == "create_box":
                new_part = self.ops.create_box(params)
                self.document.add_part(new_part)
                return self._create_response("success", "Box created.", object_ids=[new_part.id])
            
            if command == "create_cylinder":
                new_part = self.ops.create_cylinder(params)
                self.document.add_part(new_part)
                return self._create_response("success", "Cylinder created.", object_ids=[new_part.id])

            if command == "create_sphere":
                new_part = self.ops.create_sphere(params)
                self.document.add_part(new_part)
                return self._create_response("success", "Sphere created.", object_ids=[new_part.id])

            # --- Boolean Operations ---
            if command in ["fuse", "cut", "intersect"]:
                if len(selection) < 2:
                    return self._create_response("error", f"{command.capitalize()} requires at least two objects to be selected.")
                
                target_id = selection[0]
                tool_ids = selection[1:]
                
                new_part, consumed_ids = self.ops.boolean_operation(self.document, command, target_id, tool_ids)
                
                # Remove old parts, add new one
                for part_id in consumed_ids:
                    self.document.remove_part(part_id)
                self.document.add_part(new_part)
                
                return self._create_response("success", f"Boolean {command} complete.", object_ids=[new_part.id])

            # --- Transform Operations ---
            if command in ["translate", "rotate", "scale"]:
                if not selection:
                    return self._create_response("error", "Transform requires a selection.")
                
                modified_ids = self.ops.transform_operation(self.document, command, params, selection)
                return self._create_response("success", f"Transform {command} complete.", object_ids=modified_ids)

            return self._create_response("error", f"Unknown or unsupported command: {command}")

        except (CadOperationException, CapabilityException, Exception) as e:
            import traceback
            traceback.print_exc()
            return self._create_response("error", f"Operation '{command}' failed: {str(e)}")