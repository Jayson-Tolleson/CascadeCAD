import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from tools.doctor_repo import report
import os
from pathlib import Path
from quart import Quart, jsonify, render_template, request
from quart_cors import cors
from .project_api import project_bp
from .xbf_api import xbf_bp
from .collaboration import collaboration_bp

def create_app() -> Quart:
    # Explicitly configure template and static folders relative to the module package
    app = Quart(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    app = cors(app, allow_origin="*")
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
        project_name = request.args.get("project", None)
        project_data = {"name": project_name} if project_name else None
        return await render_template("project.html", project=project_data)

    @app.route("/api/status")
    async def status():
        return jsonify({
            "status": "online",
            "service": "CascadeCAD Server",
            "version": "1.0.0"
        }), 200
    @app.route("/doctor")
    async def doctor():
        return await render_template("doctor.html")

    @app.route("/api/doctor/repository")
    async def doctor_repository():
        return jsonify(report())




    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8790, debug=True)
