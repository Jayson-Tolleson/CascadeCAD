from quart import Blueprint, jsonify, request
from .engineering_assistant import EngineeringAssistant
from .command_engine import CommandDispatcher

assistant_bp = Blueprint("assistant_api", __name__)

# In production, bind this to the active session's dispatcher
mock_dispatcher = CommandDispatcher(model_context=None) 
assistant = EngineeringAssistant(mock_dispatcher)

@assistant_bp.route("/api/v1/assistant/chat", methods=["POST"])
async def api_assistant_chat():
    """Endpoint for the UI Chat/Command bar."""
    data = await request.get_json()
    query = data.get("query")
    
    if not query:
        return jsonify({"status": "error", "message": "Query cannot be empty"}), 400
        
    result = assistant.process_natural_language(query)
    return jsonify(result)

@assistant_bp.route("/api/v1/assistant/generate/script", methods=["POST"])
async def api_assistant_generate_script():
    """Generates Python automation scripts on the fly."""
    data = await request.get_json()
    intent = data.get("intent")
    
    script_code = assistant.generate_python_script(intent)
    return jsonify({"status": "success", "script": script_code})

@assistant_bp.route("/api/v1/assistant/analyze", methods=["POST"])
async def api_assistant_analyze():
    """Triggers the Engineering Intelligence review panel."""
    data = await request.get_json()
    metrics = data.get("metrics", {})
    
    analysis = assistant.analyze_model(metrics)
    return jsonify({"status": "success", "analysis": analysis})
