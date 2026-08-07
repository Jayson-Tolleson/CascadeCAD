import asyncio
from quart import Blueprint, jsonify, request, websocket

collaboration_bp = Blueprint("collaboration_api", __name__)

@collaboration_bp.route("/session", methods=["POST", "OPTIONS"])
async def collaboration_session():
    data = await request.get_json() or {}
    user_id = data.get("user_id", "user-default")
    
    return jsonify({
        "status": "success",
        "message": "Collaboration session established",
        "session_id": user_id,
        "project_visibility": data.get("project_visibility", "hidden")
    }), 200

@collaboration_bp.route("/presence", methods=["POST", "OPTIONS"])
async def update_presence():
    data = await request.get_json() or {}
    return jsonify({"status": "success", "presence": data.get("status", "active")}), 200

@collaboration_bp.websocket("/debug")
async def collaboration_debug_ws():
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive()
            await websocket.send(f"ack: {data}")
    except asyncio.CancelledError:
        raise
