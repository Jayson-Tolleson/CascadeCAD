from pathlib import Path
from quart import Blueprint, jsonify, request, Response
from .glb_engine import GLBEngine
from .xbf_document import XBFDocument
import io

render_bp = Blueprint("render_api", __name__)
WORKSPACE_ROOT = Path("./workspace")

@render_bp.route("/api/v1/render/<project_name>/<asset_id>/stream", methods=["GET"])
async def api_stream_glb(project_name, asset_id):
    """
    Streams a GLB file to the client renderer. 
    Accepts ?lod=1 query parameter to fetch simplified LOD meshes.
    """
    lod_level = int(request.args.get("lod", 0))
    xbf_path = WORKSPACE_ROOT / project_name / "xbf" / f"{asset_id}.xbf"
    
    if not xbf_path.exists():
        return jsonify({"status": "error", "message": "XBF not found"}), 404
        
    with open(xbf_path, "rb") as f:
        xbf_data = f.read()
        
    doc = XBFDocument.deserialize_from_bytes(xbf_data)
    engine = GLBEngine(doc)
    
    try:
        glb_bytes = engine.generate_glb(asset_id, use_lod=lod_level)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    # Return as an octet-stream so the browser can progressively load it
    return Response(
        glb_bytes, 
        mimetype="model/gltf-binary",
        headers={
            "Content-Disposition": f'attachment; filename="{asset_id}.glb"',
            "Cache-Control": "public, max-age=3600"
        }
    )
