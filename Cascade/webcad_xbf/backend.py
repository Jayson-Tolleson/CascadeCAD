from quart import Blueprint, request, jsonify, send_from_directory
from pathlib import Path

from .importers.manager import route_import
from .importers.project_shell import create_xbf_shell


backend_bp = Blueprint("backend", __name__)


UPLOAD_DIR = Path("/home/jayson_tolleson/Cascade/projects")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@backend_bp.route("/api/import", methods=["POST"])
async def api_import():

    files = await request.files

    if "file" not in files:
        return jsonify({
            "success": False,
            "error": "No file uploaded"
        }), 400

    file = files["file"]

    if not file.filename:
        return jsonify({
            "success": False,
            "error": "Empty filename"
        }), 400


    filename = file.filename

    file_path = UPLOAD_DIR / filename

    await file.save(str(file_path))


    import_result = route_import(filename)


    project = create_xbf_shell(
        filename,
        import_result,
        str(UPLOAD_DIR)
    )


    return jsonify({
        "success": True,
        "filename": filename,
        "path": str(file_path),
        "import": import_result,
        "project": project
    })


@backend_bp.route("/api/projects", methods=["GET"])
async def list_projects():

    projects = []

    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            projects.append({
                "name": f.name,
                "size": f.stat().st_size
            })

    return jsonify({
        "success": True,
        "projects": projects
    })


@backend_bp.route("/api/projects/<filename>", methods=["GET"])
async def get_project(filename):

    return await send_from_directory(
        UPLOAD_DIR,
        filename
    )
