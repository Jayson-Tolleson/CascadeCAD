import json
from typing import Dict, Any

from .document import Document, GeometryObject

def save_xbf(doc: Document, file_path: str, caps: Dict) -> None:
    """
    Saves the document state to a native .xbf (JSON) file.
    Note: This simple version does not embed geometry. It assumes geometry
    will be saved to separate files and referenced. For a real implementation,
    this would likely be part of a zip archive.
    """
    
    # For this pass, we'll just serialize the document structure.
    # A more advanced version would handle geometry persistence.
    
    doc_dict = {
        "format_version": "1.0",
        "id": doc.id,
        "units": doc.units,
        "metadata": doc.metadata,
        "objects": [obj.to_dict() for obj in doc.objects.values()]
    }
    
    # In a real XBF, you would now iterate through objects and save their
    # geometry to a sub-folder, adding a 'geometry_file' key to each object dict.
    # e.g., obj_dict['geometry_file'] = f"geom/{obj.id}.step"
    # For now, we raise an error if trying to save geometry.
    
    has_geometry = any(obj.geometry is not None for obj in doc.objects.values())
    if has_geometry:
        print("Warning: XBF save does not currently persist B-Rep/Mesh geometry, only the scene graph.")

    with open(file_path, 'w') as f:
        json.dump(doc_dict, f, indent=2)

def load_xbf(file_path: str, caps: Dict) -> Document:
    """
    Loads a document state from a native .xbf (JSON) file.
    """
    with open(file_path, 'r') as f:
        doc_dict = json.load(f)
        
    doc = Document()
    doc.id = doc_dict.get("id", doc.id)
    doc.units = doc_dict.get("units", doc.units)
    doc.metadata = doc_dict.get("metadata", doc.metadata)
    
    for obj_dict in doc_dict.get("objects", []):
        # This version does not load geometry, just the object structure.
        # A real implementation would read the 'geometry_file' key and load it.
        obj = GeometryObject(
            name=obj_dict.get("name", "Unnamed"),
            geometry=None, # Geometry is not persisted in this version
            geom_type=obj_dict.get("geom_type", "unknown")
        )
        obj.id = obj_dict.get("id", obj.id)
        obj.transform = obj_dict.get("transform", obj.transform)
        obj.visible = obj_dict.get("visible", obj.visible)
        obj.metadata = obj_dict.get("metadata", obj.metadata)
        doc.add_object(obj)
        
    return doc