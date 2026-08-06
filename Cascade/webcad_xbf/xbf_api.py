from pathlib import Path
from quart import Blueprint, jsonify, request
from .xbf_document import XBFDocument

xbf_bp = Blueprint("xbf_api", __name__)
WORKSPACE_ROOT = Path("./workspace")

@xbf_bp.route("/api/v1/projects/<project_name>/import", methods=["POST"])
async def api_import_to_xbf(project_name):
    """Triggers the import pipeline, translating a source CAD file into XBF storage."""
    data = await request.get_json() or {}
    source_filename = data.get("filename")
    
    if not source_filename:
        return jsonify({"status": "error", "message": "Missing filename parameter"}), 400
        
    project_dir = WORKSPACE_ROOT / project_name
    imports_dir = project_dir / "imports"
    xbf_dir = project_dir / "xbf"
    
    source_path = imports_dir / source_filename
    if not source_path.exists():
        # Fallback for testing/mocking if file hasn't been uploaded yet
        source_path = Path(source_filename)

    # Process via XBF document pipeline
    doc = XBFDocument(project_name)
    asset_id = doc.import_cad_file(str(source_path))
    
    # Save compiled XBF output
    output_xbf_path = xbf_dir / f"{asset_id}.xbf"
    doc.save(str(output_xbf_path))
    
    return jsonify({
        "status": "success",
        "asset_id": asset_id,
        "xbf_path": str(output_xbf_path),
        "mesh_stats": doc.mesh_data[asset_id]
    })
