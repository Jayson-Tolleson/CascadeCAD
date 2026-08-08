import os
import json
from typing import Dict, Any, List

from .document import Document, Part
from .adapter import CadKernelAdapter, TRIMESH_AVAILABLE
from .exceptions import ImportException, ExportException, CapabilityException
from .capabilities import Capabilities

if TRIMESH_AVAILABLE:
    import trimesh

class IoSystem:
    """Handles all import and export operations."""

    def __init__(self, adapter: CadKernelAdapter, capabilities: Capabilities):
        self.adapter = adapter
        self.capabilities = capabilities

    def import_file(self, file_path: str, original_filename: str) -> Document:
        """Imports a file and returns a new Document object."""
        _, extension = os.path.splitext(original_filename)
        extension = extension.lower().strip('.')

        if extension in self.capabilities.get_all()['import_formats']:
            doc = Document()
            doc.metadata['source_file'] = original_filename
            
            if extension == 'xbf':
                return self._import_xbf(file_path)
            
            if extension in ['step', 'stp']:
                shapes = self.adapter.import_step(file_path)
            elif extension in ['iges', 'igs']:
                shapes = self.adapter.import_iges(file_path)
            elif TRIMESH_AVAILABLE and extension in ['stl', 'obj', '3mf', 'ply', 'gltf', 'glb']:
                raise ImportException("Direct import of mesh formats to B-Rep is not yet supported. Use STEP or IGES.")
            else:
                raise ImportException(f"Unsupported or unavailable importer for format: {extension}")

            if not shapes:
                raise ImportException("No valid geometry found in the file.")

            for i, shape in enumerate(shapes):
                part_name = f"{os.path.splitext(original_filename)[0]}_{i+1}"
                part = Part(name=part_name, geometry=shape)
                doc.add_part(part)
            
            return doc
        else:
            raise ImportException(f"File format '{extension}' is not supported for import.")

    def export_file(self, doc: Document, file_format: str) -> Dict[str, Any]:
        """Exports the document to the specified format."""
        file_format = file_format.lower()
        
        if file_format not in self.capabilities.get_all()['export_formats']:
            raise CapabilityException(f"File format '{file_format}' is not supported for export.")

        filename = f"magicxbf_export_{doc.metadata.get('name', 'doc')}.{file_format}"
        
        if file_format == 'xbf':
            content = self._export_xbf(doc)
            return {"filename": filename, "file_content": content.encode('utf-8')}

        parts_to_export = doc.get_all_parts()
        geometries = [p.geometry for p in parts_to_export]
        if not geometries:
            raise ExportException("Document is empty, nothing to export.")

        # Use a temporary file for the adapter to write to
        temp_path = f"/tmp/{uuid.uuid4()}_{filename}"
        
        try:
            if file_format in ['step', 'stp']:
                self.adapter.export_step(geometries, temp_path)
            elif file_format in ['iges', 'igs']:
                self.adapter.export_iges(geometries, temp_path)
            elif file_format == 'stl':
                self.adapter.export_stl(geometries, temp_path)
            else:
                raise ExportException(f"Unsupported or unavailable exporter for format: {file_format}")

            with open(temp_path, 'rb') as f:
                file_content = f.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return {"filename": filename, "file_content": file_content}

    def _import_xbf(self, file_path: str) -> Document:
        """Loads a document from the native .xbf format."""
        doc = Document()
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        doc.xbf_version = data.get("xbf_version", "1.0")
        doc.units = data.get("units", "mm")
        doc.metadata = data.get("document_properties", {})
        
        parts_data = data.get("parts", {})
        for part_id, part_info in parts_data.items():
            brep_string = part_info.get("brep_string")
            if not brep_string:
                continue
            
            shape = self.adapter.brep_string_to_shape(brep_string)
            if shape:
                part = Part(name=part_info.get("name", "Part"), geometry=shape, part_id=part_id)
                part.transform = part_info.get("transform", [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1])
                part.display_properties = part_info.get("display", {})
                doc.add_part(part)
        return doc

    def _export_xbf(self, doc: Document) -> str:
        """Saves a document to the native .xbf format."""
        parts_dict = {}
        for part_id, part in doc.parts.items():
            brep_string = self.adapter.shape_to_brep_string(part.geometry)
            if brep_string:
                parts_dict[part_id] = {
                    "name": part.name,
                    "transform": part.transform,
                    "display": part.display_properties,
                    "brep_string": brep_string
                }

        data = {
            "xbf_version": doc.xbf_version,
            "units": doc.units,
            "document_properties": doc.metadata,
            "parts": parts_dict
        }
        return json.dumps(data, indent=2)