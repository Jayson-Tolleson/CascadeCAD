from pathlib import Path
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
