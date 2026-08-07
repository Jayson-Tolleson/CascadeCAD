from pathlib import Path
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
