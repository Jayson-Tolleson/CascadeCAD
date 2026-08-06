from pathlib import Path
from quart import Blueprint, jsonify, request
from .project import ProjectManager

project_bp = Blueprint("project_api", __name__)
WORKSPACE_ROOT = Path("./workspace")

@project_bp.route("/api/v1/projects/new", methods=["POST"])
async def api_new_project():
    data = await request.get_json() or {}
    project_name = data.get("name", "UntitledProject")
    
    try:
        manifest_path = ProjectManager.create_project(str(WORKSPACE_ROOT), project_name)
        project_data = ProjectManager.load_project(str(manifest_path))
        return jsonify({"status": "success", "project": project_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@project_bp.route("/api/v1/projects/recent", methods=["GET"])
async def api_recent_projects():
    recents = []
    if WORKSPACE_ROOT.exists():
        for manifest in WORKSPACE_ROOT.glob("**/*.ccproj"):
            recents.append({
                "name": manifest.stem,
                "path": str(manifest),
                "updated_at": manifest.stat().st_mtime,
            })
    recents.sort(key=lambda x: x["updated_at"], reverse=True)
    return jsonify(recents[:10])

@project_bp.route("/api/v1/projects/save", methods=["POST"])
async def api_save_project():
    data = await request.get_json()
    project_name = data.get("project_name")
    if not project_name:
        return jsonify({"status": "error", "message": "Missing project_name"}), 400
        
    manifest_path = WORKSPACE_ROOT / project_name / f"{project_name}.ccproj"
    
    if not manifest_path.exists():
        return jsonify({"status": "error", "message": "Project does not exist"}), 404

    ProjectManager.save_project(str(manifest_path), data)
    return jsonify({"status": "success", "saved_at": manifest_path.name})

@project_bp.route("/api/v1/project/active", methods=["GET"])
async def api_get_active_project():
    default_proj_name = "UntitledProject"
    manifest_path = WORKSPACE_ROOT / default_proj_name / f"{default_proj_name}.ccproj"
    if not manifest_path.exists():
        ProjectManager.create_project(str(WORKSPACE_ROOT), default_proj_name)
    project_data = ProjectManager.load_project(str(manifest_path))
    return jsonify(project_data)
