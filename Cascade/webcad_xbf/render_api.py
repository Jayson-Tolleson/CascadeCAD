from pathlib import Path
from quart import Blueprint, jsonify, request, Response

from .glb_engine import GLBEngine
from .xbf_document import XBFDocument


render_bp = Blueprint("render_api", __name__)

PROJECT_ROOT = Path(
    "/home/jayson_tolleson/Cascade/projects"
)


@render_bp.route(
    "/api/render/<project_id>",
    methods=["GET"]
)
async def api_render_glb(project_id):
    """
    Converts a CascadeCAD XBF project into a GLB stream.
    """

    lod_level = int(request.args.get("lod", 0))

    xbf_path = (
        PROJECT_ROOT /
        project_id /
        "document.xbf"
    )


    if not xbf_path.exists():
        return jsonify({
            "success": False,
            "error": "XBF document not found",
            "path": str(xbf_path)
        }), 404


    with open(xbf_path, "rb") as f:
        xbf_data = f.read()


    try:
        doc = XBFDocument.deserialize_from_bytes(
            xbf_data
        )

        engine = GLBEngine(doc)

        asset_id = next(
            iter(doc.mesh_data.keys())
        )

        glb_bytes = engine.generate_glb(
            asset_id,
            use_lod=lod_level
        )


    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


    return Response(
        glb_bytes,
        mimetype="model/gltf-binary",
        headers={
            "Content-Disposition":
            f'attachment; filename="{project_id}.glb"',
            "Cache-Control":
            "public, max-age=3600"
        }
    )
