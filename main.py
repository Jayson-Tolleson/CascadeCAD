import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import io

# --- Basic Configuration ---
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'step', 'stp', 'iges', 'igs', 'brep'}

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)

# --- Mock CAD Engine (Preserving from Pass 1) ---
# This represents the powerful, real CAD engine. We will not replace it.
# We will call its methods from our new API endpoints.
# For this demonstration, we use CadQuery as the backend engine.
try:
    import cadquery as cq
    logging.info("CadQuery engine loaded successfully.")
    CQ_AVAILABLE = True
except ImportError:
    logging.warning("CadQuery not found. Engine capabilities will be limited.")
    CQ_AVAILABLE = False

class CadEngine:
    """
    Represents a single CAD document and its operations.
    This class is the core of the backend logic from Pass 1.
    """
    def __init__(self):
        self.doc_id = str(uuid.uuid4())
        self.history = [cq.Workplane("XY")] # History for undo/redo
        self.selection = []
        self.assembly = cq.Assembly(name="main")
        self.object_counter = 0
        self.object_map = {} # Maps object name to cq.Shape

    def _add_to_assembly(self, shape, name=None):
        if name is None:
            self.object_counter += 1
            name = f"Solid_{self.object_counter}"
        
        # Ensure the shape is a Solid for assembly addition
        if isinstance(shape, cq.Workplane):
            solid = shape.val()
            if not isinstance(solid, cq.Solid):
                 # Try to get all solids if it's a multi-solid workplane
                solids = shape.solids().vals()
                if not solids:
                    raise ValueError("Workplane does not contain a valid solid for assembly.")
                solid = solids[0] # For now, just take the first one
        elif isinstance(shape, cq.Shape):
            solid = shape
        else:
            raise TypeError(f"Unsupported type for assembly: {type(shape)}")

        self.assembly.add(solid, name=name)
        self.object_map[name] = solid
        self.selection = [name]
        return name

    def _get_selected_workplane(self):
        if not self.selection:
            return cq.Workplane("XY")
        
        # For simplicity, we operate on the first selected object
        selected_name = self.selection[0]
        selected_obj = self.object_map.get(selected_name)
        if selected_obj:
            return cq.Workplane(selected_obj)
        return cq.Workplane("XY")

    def commit_history(self):
        # A real implementation would be more complex
        # For now, we just copy the current assembly state
        # This is a simplification of transaction management
        pass # Undo/Redo is complex, handled separately

    def create_box(self, params):
        wp = cq.Workplane("XY")
        box = wp.box(params.get('x', 10), params.get('y', 10), params.get('z', 10))
        name = self._add_to_assembly(box)
        return {"message": f"Box '{name}' created.", "selection": [name]}

    def create_cylinder(self, params):
        wp = cq.Workplane("XY")
        cyl = wp.cylinder(params.get('height', 20), params.get('radius', 5))
        name = self._add_to_assembly(cyl)
        return {"message": f"Cylinder '{name}' created.", "selection": [name]}

    def create_sphere(self, params):
        wp = cq.Workplane("XY")
        sphere = wp.sphere(params.get('radius', 10))
        name = self._add_to_assembly(sphere)
        return {"message": f"Sphere '{name}' created.", "selection": [name]}
        
    def create_cone(self, params):
        wp = cq.Workplane("XY")
        cone = wp.cone(params.get('height', 20), params.get('radius1', 10), params.get('radius2', 5))
        name = self._add_to_assembly(cone)
        return {"message": f"Cone '{name}' created.", "selection": [name]}

    def create_torus(self, params):
        wp = cq.Workplane("XY")
        torus = wp.torus(params.get('radius1', 10), params.get('radius2', 2))
        name = self._add_to_assembly(torus)
        return {"message": f"Torus '{name}' created.", "selection": [name]}

    def modify_fuse(self, params):
        if len(self.selection) < 2:
            raise ValueError("Fusion requires at least two selected objects.")
        
        base_obj_name = self.selection[0]
        other_obj_names = self.selection[1:]
        
        base_obj = self.object_map[base_obj_name]
        
        for name in other_obj_names:
            other_obj = self.object_map[name]
            base_obj = base_obj.fuse(other_obj)
            self.assembly.remove(name)
            del self.object_map[name]

        self.assembly.remove(base_obj_name)
        del self.object_map[base_obj_name]
        
        new_name = self._add_to_assembly(base_obj, name=f"Fused_{self.object_counter+1}")
        return {"message": f"Objects fused into '{new_name}'.", "selection": [new_name]}

    def modify_subtract(self, params):
        if len(self.selection) < 2:
            raise ValueError("Subtraction requires at least two selected objects (base, then tools).")
        
        base_obj_name = self.selection[0]
        tool_obj_names = self.selection[1:]
        
        base_obj = self.object_map[base_obj_name]
        
        for name in tool_obj_names:
            tool_obj = self.object_map[name]
            base_obj = base_obj.cut(tool_obj)
            self.assembly.remove(name)
            del self.object_map[name]

        self.assembly.remove(base_obj_name)
        del self.object_map[base_obj_name]

        new_name = self._add_to_assembly(base_obj, name=f"Subtracted_{self.object_counter+1}")
        return {"message": f"Objects subtracted, result is '{new_name}'.", "selection": [new_name]}

    def get_tessellation(self):
        """Generates tessellated geometry for the entire assembly."""
        if not self.assembly or not self.assembly.objects:
            return {"nodes": []}

        buffer = io.BytesIO()
        # Use GLTF as it's a modern, efficient format for web viewers
        cq.exporters.export(self.assembly, buffer, exportType='GLTF')
        buffer.seek(0)
        
        # For direct three.js JSON format, we would need a custom exporter.
        # For now, we'll let the frontend handle GLTF loading.
        # A simpler JSON format for demonstration:
        nodes = []
        for name, obj in self.assembly.objects.items():
            try:
                tess = obj.obj.tessellate()
                vertices = [v for p in tess[0] for v in (p.x, p.y, p.z)]
                faces = [i for f in tess[1] for i in f]
                nodes.append({
                    "name": name,
                    "vertices": vertices,
                    "faces": faces
                })
            except Exception as e:
                logging.error(f"Could not tessellate object {name}: {e}")

        return {"nodes": nodes}

    def import_file(self, filepath):
        """Imports a CAD file into the document."""
        try:
            shape = cq.importers.importStep(filepath)
            name = self._add_to_assembly(shape, name=os.path.basename(filepath))
            return {"message": f"Imported '{os.path.basename(filepath)}' as '{name}'.", "selection": [name]}
        except Exception as e:
            logging.error(f"Failed to import {filepath}: {e}")
            raise ValueError(f"Unsupported format or corrupt file: {e}")

    def export_file(self, filepath, export_format):
        """Exports the document to a specified format."""
        if not self.assembly.objects:
            raise ValueError("Cannot export an empty document.")

        fmt = export_format.upper()
        
        # For single-part export, we fuse everything first.
        # A more advanced implementation would handle assemblies correctly.
        export_obj = self.assembly
        if len(self.assembly.objects) > 1 and fmt in ['STEP', 'IGES', 'STL']:
             # Fuse all objects for monolithic export formats
            all_shapes = [item.obj for item in self.assembly.objects.values()]
            fused_shape = all_shapes[0]
            for i in range(1, len(all_shapes)):
                fused_shape = fused_shape.fuse(all_shapes[i])
            export_obj = fused_shape

        try:
            cq.exporters.export(export_obj, filepath, exportType=fmt)
            return True
        except Exception as e:
            logging.error(f"Export failed for format {fmt}: {e}")
            raise IOError(f"Engine failed to export to {fmt}.")

    def get_info(self, params):
        if not self.selection:
            return {"message": "No object selected."}
        name = self.selection[0]
        obj = self.object_map.get(name)
        if not obj:
            return {"message": f"Selected object '{name}' not found."}
        
        bb = obj.BoundingBox()
        info_text = (
            f"Info for: {name}\n"
            f"Type: {type(obj).__name__}\n"
            f"Center: ({bb.center.x:.2f}, {bb.center.y:.2f}, {bb.center.z:.2f})\n"
            f"Size: ({bb.xlen:.2f}, {bb.ylen:.2f}, {bb.zlen:.2f})"
        )
        return {"message": info_text}
        
    def assistant_command(self, text):
        text = text.lower().strip()
        import re
        # This is a simple parser, a real one would use NLP
        m = re.match(r"create a (\d+\.?\d*) ?mm box", text)
        if m:
            size = float(m.group(1))
            return self.create_box({'x': size, 'y': size, 'z': size})

        m = re.match(r"create a cylinder (\d+\.?\d*) mm diameter and (\d+\.?\d*) mm tall", text)
        if m:
            radius = float(m.group(1)) / 2.0
            height = float(m.group(2))
            return self.create_cylinder({'radius': radius, 'height': height})
        
        m = re.match(r"create a sphere with radius (\d+\.?\d*)", text)
        if m:
            radius = float(m.group(1))
            return self.create_sphere({'radius': radius})

        raise ValueError("Assistant could not understand the command.")


# --- Document Management ---
# In a real app, this would use a database or proper session management
documents = {}

def get_doc(doc_id):
    if doc_id not in documents:
        raise ValueError("Document not found or session expired.")
    return documents[doc_id]

# --- API Routes ---

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/api/engine/capabilities')
def get_capabilities():
    """Reports what the current backend engine can do."""
    return jsonify({
        "engine": "CadQuery" if CQ_AVAILABLE else "None",
        "import_formats": ["STEP", "STP", "IGES", "IGS", "BREP"] if CQ_AVAILABLE else [],
        "export_formats": ["STEP", "STL", "3MF", "SVG", "GLTF"] if CQ_AVAILABLE else [],
        "commands": {
            "create_box": CQ_AVAILABLE,
            "create_cylinder": CQ_AVAILABLE,
            "create_sphere": CQ_AVAILABLE,
            "create_cone": CQ_AVAILABLE,
            "create_torus": CQ_AVAILABLE,
            "modify_fuse": CQ_AVAILABLE,
            "modify_subtract": CQ_AVAILABLE,
            "get_info": CQ_AVAILABLE,
            "assistant": CQ_AVAILABLE,
            "undo": False, # Complex to implement correctly
            "redo": False,
            "draft_tools": False, # Requires 2D sketcher integration
            "transform_tools": False, # Requires interactive gizmos/state
            "share_tools": False, # Requires external services
        }
    })

@app.route('/api/document/new', methods=['POST'])
def new_document():
    doc_id = str(uuid.uuid4())
    documents[doc_id] = CadEngine()
    logging.info(f"Created new document: {doc_id}")
    return jsonify({"docId": doc_id, "message": "New document created."})

@app.route('/api/document/<doc_id>/import', methods=['POST'])
def import_file(doc_id):
    engine = get_doc(doc_id)
    if 'cad-file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['cad-file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"File type '{ext}' not supported."}), 400
            
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}_{filename}")
        file.save(filepath)
        
        try:
            result = engine.import_file(filepath)
            tessellation = engine.get_tessellation()
            return jsonify({**result, "tessellation": tessellation})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

@app.route('/api/document/<doc_id>/export', methods=['GET'])
def export_file_route(doc_id):
    engine = get_doc(doc_id)
    export_format = request.args.get('format', 'step').lower()
    
    # MagicXBF is the internal project format, we can treat it as STEP for now
    if export_format == 'xbf':
        export_format = 'step'

    # Define file extensions
    extensions = {'step': 'step', 'iges': 'igs', 'stl': 'stl', '3mf': '3mf'}
    if export_format not in extensions:
        return jsonify({"error": "Unsupported export format"}), 400

    filename = f"magicxbf_export_{doc_id}.{extensions[export_format]}"
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)

    try:
        engine.export_file(filepath, export_format)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/document/<doc_id>/command', methods=['POST'])
def handle_command(doc_id):
    engine = get_doc(doc_id)
    data = request.get_json()
    command = data.get('command')
    params = data.get('params', {})

    # Update selection state from client
    if 'selection' in params:
        engine.selection = params['selection']

    try:
        # Command dispatch
        if command == 'create_box':
            result = engine.create_box(params)
        elif command == 'create_cylinder':
            result = engine.create_cylinder(params)
        elif command == 'create_sphere':
            result = engine.create_sphere(params)
        elif command == 'create_cone':
            result = engine.create_cone(params)
        elif command == 'create_torus':
            result = engine.create_torus(params)
        elif command == 'modify_fuse':
            result = engine.modify_fuse(params)
        elif command == 'modify_subtract':
            result = engine.modify_subtract(params)
        elif command == 'get_info':
            result = engine.get_info(params)
        elif command == 'assistant_command':
            result = engine.assistant_command(params.get('text', ''))
        elif command == 'tessellate':
            result = {"message": "Scene tessellated."}
        else:
            return jsonify({"error": f"Unknown command: {command}"}), 404
        
        tessellation = engine.get_tessellation()
        # Update selection in response
        result['selection'] = engine.selection
        return jsonify({**result, "tessellation": tessellation})

    except Exception as e:
        logging.error(f"Command '{command}' failed: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)