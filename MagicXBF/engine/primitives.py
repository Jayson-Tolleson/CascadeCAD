from typing import Dict, Any

from .document import Document, GeometryObject
from .io import _check_capability

def create_box(doc: Document, params: Dict) -> Dict[str, Any]:
    _check_capability(doc.engine.capabilities, 'brep', 'box', 'primitives')
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    
    try:
        dx = float(params.get('dx', 10.0))
        dy = float(params.get('dy', 10.0))
        dz = float(params.get('dz', 10.0))
        
        box_shape = BRepPrimAPI_MakeBox(dx, dy, dz).Shape()
        
        obj = GeometryObject("Box", box_shape, 'brep')
        doc.add_object(obj)
        
        return {
            "status": "ok",
            "operation": "create_box",
            "message": "Box created successfully.",
            "created": [obj.to_dict()]
        }
    except Exception as e:
        return {"status": "error", "operation": "create_box", "message": str(e)}

def create_cylinder(doc: Document, params: Dict) -> Dict[str, Any]:
    _check_capability(doc.engine.capabilities, 'brep', 'cylinder', 'primitives')
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    try:
        radius = float(params.get('radius', 5.0))
        height = float(params.get('height', 20.0))
        
        cyl_shape = BRepPrimAPI_MakeCylinder(radius, height).Shape()
        
        obj = GeometryObject("Cylinder", cyl_shape, 'brep')
        doc.add_object(obj)
        
        return {
            "status": "ok",
            "operation": "create_cylinder",
            "message": "Cylinder created successfully.",
            "created": [obj.to_dict()]
        }
    except Exception as e:
        return {"status": "error", "operation": "create_cylinder", "message": str(e)}

def create_sphere(doc: Document, params: Dict) -> Dict[str, Any]:
    _check_capability(doc.engine.capabilities, 'brep', 'sphere', 'primitives')
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere

    try:
        radius = float(params.get('radius', 10.0))
        
        sphere_shape = BRepPrimAPI_MakeSphere(radius).Shape()
        
        obj = GeometryObject("Sphere", sphere_shape, 'brep')
        doc.add_object(obj)
        
        return {
            "status": "ok",
            "operation": "create_sphere",
            "message": "Sphere created successfully.",
            "created": [obj.to_dict()]
        }
    except Exception as e:
        return {"status": "error", "operation": "create_sphere", "message": str(e)}

def create_cone(doc: Document, params: Dict) -> Dict[str, Any]:
    _check_capability(doc.engine.capabilities, 'brep', 'cone', 'primitives')
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone

    try:
        r1 = float(params.get('r1', 10.0))
        r2 = float(params.get('r2', 0.0))
        height = float(params.get('height', 20.0))
        
        cone_shape = BRepPrimAPI_MakeCone(r1, r2, height).Shape()
        
        obj = GeometryObject("Cone", cone_shape, 'brep')
        doc.add_object(obj)
        
        return {
            "status": "ok",
            "operation": "create_cone",
            "message": "Cone created successfully.",
            "created": [obj.to_dict()]
        }
    except Exception as e:
        return {"status": "error", "operation": "create_cone", "message": str(e)}

def create_torus(doc: Document, params: Dict) -> Dict[str, Any]:
    _check_capability(doc.engine.capabilities, 'brep', 'torus', 'primitives')
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeTorus

    try:
        r1 = float(params.get('r1', 10.0))
        r2 = float(params.get('r2', 2.0))
        
        torus_shape = BRepPrimAPI_MakeTorus(r1, r2).Shape()
        
        obj = GeometryObject("Torus", torus_shape, 'brep')
        doc.add_object(obj)
        
        return {
            "status": "ok",
            "operation": "create_torus",
            "message": "Torus created successfully.",
            "created": [obj.to_dict()]
        }
    except Exception as e:
        return {"status": "error", "operation": "create_torus", "message": str(e)}