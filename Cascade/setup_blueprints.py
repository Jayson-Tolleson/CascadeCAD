import os
from pathlib import Path

# Ensure webcad_xbf package directory exists
os.makedirs("webcad_xbf", exist_ok=True)

files = {
    "webcad_xbf/app.py": '''import os
from pathlib import Path
from quart import Quart, jsonify
from quart_cors import CORS

from .project_api import project_bp
from .xbf_api import xbf_bp
from .collaboration import collaboration_bp

def create_app() -> Quart:
    app = Quart(__name__)
    CORS(app)

    app.config["CASCADE_STORAGE_DIR"] = Path(
        os.getenv("CASCADE_STORAGE_DIR", "/home/jayson_tolleson/Cascade/projects")
    )
    app.config["CASCADE_STORAGE_DIR"].mkdir(parents=True, exist_ok=True)

    app.register_blueprint(project_bp, url_prefix="/api/v1/projects")
    app.register_blueprint(xbf_bp, url_prefix="/api/v1/projects")
    app.register_blueprint(collaboration_bp, url_prefix="/api/v1/collaboration")

    @app.route("/")
    @app.route("/cascade-cad")
    async def index():
        return jsonify({
            "status": "online",
            "service": "CascadeCAD Server",
            "version": "1.0.0"
        }), 200

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
''',

    "webcad_xbf/project_api.py": '''from pathlib import Path
from quart import Blueprint, jsonify, request, current_app
from .store import Store

project_bp = Blueprint("project_api", __name__)
store = Store()

@project_bp.route("/", methods=["GET"])
async def list_projects():
    storage_dir: Path = current_app.config["CASCADE_STORAGE_DIR"]
    projects = []
    if storage_dir.exists():
        for item in storage_dir.iterdir():
            if item.is_dir():
                manifest_path = item / "project.json"
                projects.append({
                    "id": item.name,
                    "has_manifest": manifest_path.exists()
                })
    return jsonify({"status": "success", "projects": projects}), 200

@project_bp.route("/new", methods=["POST"])
async def create_project():
    data = await request.get_json() or {}
    name = data.get("name", "UntitledProject")
    source = data.get("source_filename", "model.step")
    
    project = store.create_project(name, source)
    return jsonify({"status": "success", "project": project}), 201

@project_bp.route("/<project_id>", methods=["GET"])
async def get_project(project_id: str):
    try:
        manifest = store.get_project(project_id)
        return jsonify({"status": "success", "project": manifest}), 200
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "Project not found"}), 404
''',

    "webcad_xbf/xbf_api.py": '''from pathlib import Path
from quart import Blueprint, jsonify, request, current_app
from .xbf_document import XBFDocument

xbf_bp = Blueprint("xbf_api", __name__)

@xbf_bp.route("/<project_id>/import", methods=["POST"])
async def import_cad_model(project_id: str):
    data = await request.get_json() or {}
    source_filename = data.get("filename")
    
    if not source_filename:
        return jsonify({"status": "error", "message": "Missing filename parameter"}), 400

    storage_path = current_app.config["CASCADE_STORAGE_DIR"] / project_id
    source_path = storage_path / source_filename
    
    if not source_path.exists():
        return jsonify({"status": "error", "message": f"File {source_filename} not found in project storage"}), 404

    doc = XBFDocument()
    asset_id = doc.import_cad_file(str(source_path))
    
    return jsonify({
        "status": "success",
        "message": f"Successfully processed {source_filename}",
        "asset_id": asset_id,
        "mesh_stats": doc.mesh_data.get(asset_id, {})
    }), 200
''',

    "webcad_xbf/collaboration.py": '''from quart import Blueprint, jsonify, request

collaboration_bp = Blueprint("collaboration_api", __name__)

@collaboration_bp.route("/session", methods=["POST", "OPTIONS"])
async def collaboration_session():
    data = await request.get_json() or {}
    user_id = data.get("user_id", "user-default")
    
    return jsonify({
        "status": "success",
        "message": "Collaboration session established",
        "session_id": user_id,
        "project_visibility": data.get("project_visibility", "hidden")
    }), 200

@collaboration_bp.route("/presence", methods=["POST", "OPTIONS"])
async def update_presence():
    data = await request.get_json() or {}
    return jsonify({"status": "success", "presence": data.get("status", "active")}), 200
'''
}

def main():
    for filepath, content in files.items():
        path = Path(filepath)
        path.write_text(content, encoding="utf-8")
        print(f"[SUCCESS] Written: {path}")

if __name__ == "__main__":
    main()
