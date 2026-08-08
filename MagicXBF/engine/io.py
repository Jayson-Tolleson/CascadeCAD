from typing import Dict, Any

from .document import Document, GeometryObject

# --- Helper Functions ---

def _check_capability(caps: Dict, category: str, feature: str, op_type: str):
    """Checks for a capability and raises an exception if not available."""
    if not caps[category].get("available", False):
        raise RuntimeError(f"{op_type.capitalize()} requires the '{caps[category]['kernel'] or 'a compatible'}' {category} kernel, which is not installed.")
    if feature not in caps[category].get(op_type, []):
        raise RuntimeError(f"{op_type.capitalize()} for '{feature}' format is not supported by the current configuration.")

# --- B-Rep Import/Export (pythonOCC) ---

def import_step(file_path: str, caps: Dict) -> Document:
    _check_capability(caps, 'brep', 'step', 'import')
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
    
    reader = STEPControl_Reader()
    status = reader.ReadFile(file_path)

    if status != IFSelect_RetDone:
        raise RuntimeError("STEP file could not be read.")

    reader.WS().TransferReader().GetObject().SetTraceLevel(0)
    reader.TransferRoots()
    
    doc = Document()
    doc.source_file = file_path
    
    num_shapes = reader.NbShapes()
    for i in range(1, num_shapes + 1):
        shape = reader.Shape(i)
        name = f"Solid_{i}"
        geom_obj = GeometryObject(name, shape, 'brep')
        doc.add_object(geom_obj)
        
    if num_shapes == 0:
        raise RuntimeError("No valid shapes found in the STEP file.")
        
    return doc

def export_step(doc: Document, file_path: str, caps: Dict):
    _check_capability(caps, 'brep', 'step', 'export')
    from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCC.Core.Interface import Interface_Static
    
    writer = STEPControl_Writer()
    Interface_Static.SetCVal("write.step.schema", "AP214")

    for obj in doc.objects.values():
        if obj.geom_type == 'brep' and obj.geometry:
            writer.Transfer(obj.geometry, STEPControl_AsIs)

    status = writer.Write(file_path)
    if status != 1: # IFSelect_RetDone is 1
        raise RuntimeError("Failed to write STEP file.")

def import_iges(file_path: str, caps: Dict) -> Document:
    _check_capability(caps, 'brep', 'iges', 'import')
    from OCC.Core.IGESControl import IGESControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    
    reader = IGESControl_Reader()
    status = reader.ReadFile(file_path)

    if status != IFSelect_RetDone:
        raise RuntimeError("IGES file could not be read.")

    reader.TransferRoots()
    
    doc = Document()
    doc.source_file = file_path
    
    num_shapes = reader.NbShapes()
    for i in range(1, num_shapes + 1):
        shape = reader.Shape(i)
        name = f"Solid_{i}"
        geom_obj = GeometryObject(name, shape, 'brep')
        doc.add_object(geom_obj)
        
    if num_shapes == 0:
        raise RuntimeError("No valid shapes found in the IGES file.")
        
    return doc

def export_iges(doc: Document, file_path: str, caps: Dict):
    _check_capability(caps, 'brep', 'iges', 'export')
    from OCC.Core.IGESControl import IGESControl_Writer
    
    writer = IGESControl_Writer()
    for obj in doc.objects.values():
        if obj.geom_type == 'brep' and obj.geometry:
            writer.AddShape(obj.geometry)

    writer.Write(file_path)

# --- Mesh Import/Export (trimesh) ---

def import_stl(file_path: str, caps: Dict) -> Document:
    _check_capability(caps, 'mesh', 'stl', 'import')
    import trimesh
    
    mesh = trimesh.load_mesh(file_path)
    if not isinstance(mesh, trimesh.Trimesh) or mesh.is_empty:
        raise RuntimeError("Failed to load a valid mesh from the STL file.")
        
    doc = Document()
    doc.source_file = file_path
    geom_obj = GeometryObject("STL_Mesh", mesh, 'mesh')
    doc.add_object(geom_obj)
    return doc

def export_stl(doc: Document, file_path: str, caps: Dict):
    # STL can be exported from B-Rep or Mesh
    if not (caps['brep']['available'] or caps['mesh']['available']):
        raise RuntimeError("STL export requires either a B-Rep or Mesh kernel.")

    if caps['mesh']['available']:
        import trimesh
        # Combine all meshes in the document into one for export
        meshes_to_export = []
        for obj in doc.objects.values():
            if obj.geom_type == 'mesh' and obj.geometry:
                meshes_to_export.append(obj.geometry)
            elif obj.geom_type == 'brep' and obj.geometry and caps['brep']['available']:
                # Tessellate B-Rep to mesh for export
                from . import tessellation
                mesh_data = tessellation.tessellate_object(obj, 0.1, caps)
                if mesh_data:
                    vertices = mesh_data['vertices']
                    indices = mesh_data['indices']
                    faces = [indices[i:i+3] for i in range(0, len(indices), 3)]
                    temp_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                    meshes_to_export.append(temp_mesh)
        
        if not meshes_to_export:
            raise RuntimeError("No exportable mesh or B-Rep geometry found in the document.")
            
        combined_mesh = trimesh.util.concatenate(meshes_to_export)
        combined_mesh.export(file_path, file_type='stl')
    
    elif caps['brep']['available']:
        # Fallback to pythonOCC's STL writer if trimesh is not available
        from OCC.Core.StlAPI import StlAPI_Writer
        stl_writer = StlAPI_Writer()
        stl_writer.SetASCIIMode(False) # Binary is better
        for obj in doc.objects.values():
            if obj.geom_type == 'brep' and obj.geometry:
                if not stl_writer.Write(obj.geometry, file_path):
                     raise RuntimeError(f"Failed to write object {obj.name} to STL.")
    else:
        raise RuntimeError("STL export failed, no suitable kernel found.")


def import_obj(file_path: str, caps: Dict) -> Document:
    _check_capability(caps, 'mesh', 'obj', 'import')
    import trimesh
    
    # trimesh can load OBJ files as a scene or a single mesh
    loaded = trimesh.load(file_path, force='scene')
    
    doc = Document()
    doc.source_file = file_path
    
    if isinstance(loaded, trimesh.Trimesh):
        geom_obj = GeometryObject(loaded.metadata.get('name', 'OBJ_Mesh'), loaded, 'mesh')
        doc.add_object(geom_obj)
    elif isinstance(loaded, trimesh.Scene):
        for name, mesh in loaded.geometry.items():
            geom_obj = GeometryObject(name, mesh, 'mesh')
            doc.add_object(geom_obj)
    else:
        raise RuntimeError("Failed to load a valid mesh or scene from the OBJ file.")
        
    if not doc.objects:
        raise RuntimeError("No geometry found in OBJ file.")
        
    return doc

def import_3mf(file_path: str, caps: Dict) -> Document:
    _check_capability(caps, 'mesh', '3mf', 'import')
    import trimesh
    
    scene = trimesh.load(file_path, force='scene')
    doc = Document()
    doc.source_file = file_path
    
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        mesh = scene.geometry[geometry_name]
        geom_obj = GeometryObject(geometry_name, mesh, 'mesh')
        # TODO: Apply transform from scene graph
        doc.add_object(geom_obj)
        
    if not doc.objects:
        raise RuntimeError("No geometry found in 3MF file.")
        
    return doc

def export_3mf(doc: Document, file_path: str, caps: Dict):
    _check_capability(caps, 'mesh', '3mf', 'export')
    import trimesh
    
    scene = trimesh.Scene()
    for obj in doc.objects.values():
        mesh_to_add = None
        if obj.geom_type == 'mesh' and obj.geometry:
            mesh_to_add = obj.geometry
        elif obj.geom_type == 'brep' and obj.geometry and caps['brep']['available']:
            from . import tessellation
            mesh_data = tessellation.tessellate_object(obj, 0.1, caps)
            if mesh_data:
                vertices = mesh_data['vertices']
                indices = mesh_data['indices']
                faces = [indices[i:i+3] for i in range(0, len(indices), 3)]
                mesh_to_add = trimesh.Trimesh(vertices=vertices, faces=faces)
        
        if mesh_to_add:
            scene.add_geometry(mesh_to_add, node_name=obj.id, geom_name=obj.name)
            
    if not scene.geometry:
        raise RuntimeError("No exportable geometry found in the document.")
        
    scene.export(file_path, file_type='3mf')