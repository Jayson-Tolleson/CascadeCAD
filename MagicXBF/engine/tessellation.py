from typing import Dict, Any, Optional
import numpy as np

from .document import GeometryObject

def tessellate_object(obj: GeometryObject, quality: float, caps: Dict) -> Optional[Dict[str, Any]]:
    """
    Tessellates a single GeometryObject based on its type.
    `quality` is a linear deflection value. Smaller is higher quality.
    """
    if obj.geom_type == 'brep':
        if not caps['brep']['available']:
            raise RuntimeError("Cannot tessellate B-Rep object: pythonOCC kernel not available.")
        return _tessellate_brep(obj, quality)
    elif obj.geom_type == 'mesh':
        if not caps['mesh']['available']:
            raise RuntimeError("Cannot process mesh object: trimesh kernel not available.")
        return _tessellate_mesh(obj)
    return None

def _tessellate_brep(obj: GeometryObject, quality: float) -> Dict[str, Any]:
    """Tessellates a B-Rep shape (TopoDS_Shape) using pythonOCC."""
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopoDS import topods_Face
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopLoc import TopLoc_Location
    
    shape = obj.geometry
    
    # Apply the object's transform to the shape before tessellating
    # TODO: Implement full transformation logic
    
    # Perform meshing
    mesh = BRepMesh_IncrementalMesh(shape, quality)
    mesh.Perform()
    if not mesh.IsDone():
        raise RuntimeError(f"Tessellation failed for object {obj.name}")

    # Extract mesh data
    vertices = []
    normals = []
    indices = []
    vert_offset = 0

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = topods_Face(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)

        if triangulation is None:
            explorer.Next()
            continue

        tris = triangulation.Triangles()
        nodes = triangulation.Nodes()
        
        # Get normals if available
        if triangulation.HasUVNodes():
            face_normals = []
            # This part can be complex; for now, we'll compute them later if needed
            # or rely on what Three.js can compute. A simplified approach:
            if triangulation.HasNormals():
                all_normals = triangulation.Normals()
                for i in range(1, all_normals.Length() + 1):
                    n = all_normals.Value(i)
                    face_normals.extend([n.X(), n.Y(), n.Z()])
            
        # Transform vertices by face location
        trsf = location.Transformation()
        for i in range(1, nodes.Length() + 1):
            p = nodes.Value(i)
            p.Transform(trsf)
            vertices.extend([p.X(), p.Y(), p.Z()])

        # Create indices
        for i in range(1, tris.Length() + 1):
            tri = tris.Value(i)
            # OCC indices are 1-based, convert to 0-based
            i1, i2, i3 = tri.Value(1) - 1, tri.Value(2) - 1, tri.Value(3) - 1
            indices.extend([i1 + vert_offset, i2 + vert_offset, i3 + vert_offset])
        
        vert_offset += nodes.Length()
        explorer.Next()

    if not vertices:
        return None # No geometry was generated

    # Use numpy for efficient normal calculation if they weren't available
    if not normals and len(vertices) > 0:
        verts_np = np.array(vertices).reshape(-1, 3)
        indices_np = np.array(indices).reshape(-1, 3)
        
        # Create a temporary trimesh object just for normal calculation
        import trimesh
        mesh_for_normals = trimesh.Trimesh(vertices=verts_np, faces=indices_np, process=False)
        mesh_for_normals.refresh() # This computes face and vertex normals
        
        # We need per-vertex normals, but trimesh stores them per-vertex
        # We need to expand them to match the vertex buffer layout
        vertex_normals = mesh_for_normals.vertex_normals
        normals = vertex_normals[indices_np.flatten()].flatten().tolist()
        
        # Re-arrange vertices to be non-indexed to match the expanded normals
        vertices = verts_np[indices_np.flatten()].flatten().tolist()
        indices = list(range(len(vertices) // 3))


    return {
        "id": obj.id,
        "name": obj.name,
        "vertices": vertices,
        "normals": normals,
        "indices": indices,
        "transform": obj.transform
    }

def _tessellate_mesh(obj: GeometryObject) -> Dict[str, Any]:
    """Extracts mesh data from a trimesh object."""
    mesh = obj.geometry
    
    # Trimesh might not have vertex normals computed
    if not hasattr(mesh, 'vertex_normals') or len(mesh.vertex_normals) != len(mesh.vertices):
        mesh.fix_normals()

    # We need to expand vertices and normals to match a non-indexed buffer
    # for simple rendering in Three.js, similar to the B-Rep path.
    flat_vertices = mesh.vertices[mesh.faces.flatten()].flatten().tolist()
    flat_normals = mesh.vertex_normals[mesh.faces.flatten()].flatten().tolist()
    flat_indices = list(range(len(flat_vertices) // 3))

    return {
        "id": obj.id,
        "name": obj.name,
        "vertices": flat_vertices,
        "normals": flat_normals,
        "indices": flat_indices,
        "transform": obj.transform
    }