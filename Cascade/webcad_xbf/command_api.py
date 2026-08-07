from quart import Blueprint, jsonify, request
from .command_engine import CommandDispatcher

# In a real app, this dispatcher is instantiated globally or per-session with the active XBF model
# mock_context = XBFDocument("CurrentSession")
# global_dispatcher = CommandDispatcher(mock_context)

command_bp = Blueprint("command_api", __name__)

@command_bp.route("/api/v1/commands/execute", methods=["POST"])
async def api_execute_command():
    data = await request.get_json()
    command_name = data.get("command")
    params = data.get("params", {})
    
    # success = global_dispatcher.execute(command_name, **params)
    # Mocking success for the API skeleton
    success = True
    
    if success:
        return jsonify({"status": "success", "executed": command_name})
    return jsonify({"status": "error", "message": "Command execution failed"}), 400

@command_bp.route("/api/v1/commands/undo", methods=["POST"])
async def api_undo_command():
    # success = global_dispatcher.undo()
    return jsonify({"status": "success", "action": "undo"})

@command_bp.route("/api/v1/commands/redo", methods=["POST"])
async def api_redo_command():
    # success = global_dispatcher.redo()
    return jsonify({"status": "success", "action": "redo"})
