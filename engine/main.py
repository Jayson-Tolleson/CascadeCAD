from typing import Dict, Any, List, Optional
import re

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
                part.tessellation_cache = self.tessellator.tessellate_part(part)

            if part.tessellation_cache and part.tessellation_cache.get('vertices'):
                geom_data = {
                    "uuid": part.id,
                    "name": part.name,
                    "positions": part.tessellation_cache['vertices'],
                    "indices": part.tessellation_cache['indices'],
                    "normals": part.tessellation_cache['normals'],
                    "color": part.display_properties.get('color', [0.8, 0.8, 0.8]),
                    "opacity": part.display_properties.get('opacity', 1.0)
                }
                all_geometries.append(geom_data)
        
        return {"mesh_buffers": all_geometries, "parts": [p.to_dict() for p in self.document.get_all_parts()]}

    def execute_command(self, command: str, params: Dict, selection: List[str]) -> Dict:
        """Executes a generic CAD command."""
        try:
            # --- Primitive Creation ---
            if command.startswith("create_"):
                primitive_type = command.split("_")[1]
                new_part = self.ops.create_primitive(primitive_type, params)
                self.document.add_part(new_part)
                return self._create_response("success", f"{primitive_type.capitalize()} created.", object_ids=[new_part.id])

            # --- Boolean Operations ---
            if command in ["fuse", "cut", "intersect"]:
                if len(selection) < 2:
                    return self._create_response("error", f"{command.capitalize()} requires at least two objects to be selected.")
                
                target_id = selection[0]
                tool_ids = selection[1:]
                
                new_part, consumed_ids = self.ops.boolean_operation(self.document, command, target_id, tool_ids)
                
                for part_id in consumed_ids:
                    self.document.remove_part(part_id)
                self.document.add_part(new_part)
                
                return self._create_response("success", f"Boolean {command} complete.", object_ids=[new_part.id])

            return self._create_response("error", f"Unknown or unsupported command: {command}")

        except (CadOperationException, CapabilityException, Exception) as e:
            import traceback
            traceback.print_exc()
            return self._create_response("error", f"Operation '{command}' failed: {str(e)}")

    def execute_assistant_command(self, prompt: str) -> Dict:
        """Parses a natural language prompt and executes the corresponding command."""
        prompt = prompt.lower().strip()

        # "Create a 50 mm box."
        m = re.match(r"create a (\d+\.?\d*) ?mm box", prompt)
        if m:
            size = float(m.group(1))
            params = {'dx': size, 'dy': size, 'dz': size}
            return self.execute_command('create_box', params, [])

        # "Create a cylinder 20 mm diameter and 50 mm tall."
        m = re.match(r"create a cylinder (\d+\.?\d*) ?mm diameter and (\d+\.?\d*) ?mm tall", prompt)
        if m:
            radius = float(m.group(1)) / 2.0
            height = float(m.group(2))
            params = {'radius': radius, 'height': height}
            return self.execute_command('create_cylinder', params, [])

        # "Subtract the cylinder from the box."
        if "subtract" in prompt or "cut" in prompt:
            parts = self.document.get_all_parts()
            if len(parts) >= 2:
                # Simple assumption: last created is tool, second to last is target
                selection = [p.id for p in sorted(parts, key=lambda x: x.name, reverse=True)]
                return self.execute_command('cut', {}, selection)
            else:
                return self._create_response("error", "Subtraction requires at least two objects.", data={"prompt": prompt})

        # "Fuse" or "union"
        if "fuse" in prompt or "union" in prompt or "combine" in prompt:
            parts = self.document.get_all_parts()
            if len(parts) >= 2:
                selection = [p.id for p in parts]
                return self.execute_command('fuse', {}, selection)
            else:
                return self._create_response("error", "Fuse requires at least two objects.", data={"prompt": prompt})
        
        # "Fillet all edges at 2 mm."
        if "fillet" in prompt:
            return self._create_response("error", "Fillet operation is not yet implemented (PENDING BACKEND).", data={"prompt": prompt})

        # "What is the mass of this assembly?"
        if "mass" in prompt:
            return self._create_response("error", "Mass calculation is not yet implemented (PENDING BACKEND).", data={"prompt": prompt})

        return self._create_response("error", "Assistant could not understand the command.", data={"prompt": prompt})