from .assistant_api import assistant_bp
from .command_api import command_bp
from .project_api import project_bp
from quart import Quart, render_template
from .render_api import render_bp
from .xbf_api import xbf_bp

# Point static_folder directly into the webcad-xbf directory
# Point static_folder and template_folder directly into the webcad_xbf directory
app = Quart(__name__, template_folder="templates", static_folder="static")

app.register_blueprint(project_bp, url_prefix="/cascade-cad")
app.register_blueprint(xbf_bp, url_prefix="/cascade-cad")
app.register_blueprint(render_bp, url_prefix="/cascade-cad")
app.register_blueprint(command_bp, url_prefix="/cascade-cad")
app.register_blueprint(assistant_bp, url_prefix="/cascade-cad")


@app.route("/")
@app.route("/cascade-cad/")
@app.route("/cascade-cad")
async def index():
  return await render_template("project.html", chunk_bytes=5242880, project={"name": "Untitled Project"})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8790, debug=True)


@app.route("/cascade-cad/api/projects/", methods=["GET"])
@app.route("/api/v1/projects/", methods=["GET"])
async def api_projects_compat():
    try:
        from Cascade.webcad_xbf.api.project_api import api_recent_projects
        return await api_recent_projects()
    except Exception:
        return {"projects": []}, 200


@app.route("/cascade-cad/api/v1/collaboration/join", methods=["POST", "OPTIONS"])
@app.route("/cascade-cad/api/collaboration/join", methods=["POST", "OPTIONS"])
@app.route("/api/v1/collaboration/join", methods=["POST", "OPTIONS"])
async def api_collab_join_compat():
    return {"status": "success", "message": "Collaboration session joined", "session_id": "default-session"}, 200
