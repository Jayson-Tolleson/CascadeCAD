import asyncio
import json
import os
import uuid
from quart import Quart, request, jsonify, send_from_directory, make_response
from quart_cors import cors

# Import the new, layered MagicXBF engine
import engine

# --- App Initialization ---
app = Quart(__name__, static_folder='static', template_folder='templates')
app = cors(app, allow_origin="*") # Allow all origins for development
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit
app.config["UPLOAD_FOLDER"] = "/tmp/magicxbf_uploads"

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize the single, stateful CAD Engine instance
# This call performs capability detection on startup.
CAD_ENGINE = engine.initialize()

# --- Helper Functions ---
def create_structured_response(status, operation, message, data=None, object_ids=None):
    """Creates a standardized JSON response."""
    response = {
        "status": status,
        "operation": operation,
        "message": message,
        "data": data or {},
        "object_ids": object_ids or []
    }
    return jsonify(response)

# --- API Endpoints ---

@app.route('/api/status', methods=['GET'])
async def api_status():
    """Returns the current status of the backend engine."""
    return create_structured_response("success", "status", "Engine is running.")

@app.route('/api/capabilities', methods=['GET'])
async def api_capabilities():
    """Returns a dictionary of available engine capabilities."""
    caps = await asyncio.to_thread(CAD_ENGINE.get_capabilities)
    return create_structured_response("success", "get_capabilities", "Successfully retrieved engine capabilities.", data=caps)

@app.route('/api/command', methods=['POST'])
async def api_command():
    """Main endpoint for executing CAD operations."""
    try:
        payload = await request.get_json()
        if not payload or "command" not in payload:
            return await make_response(create_structured_response("error", "command", "Invalid command payload."), 400)

        command = payload.get("command")
        params = payload.get("params", {})
        selection = payload.get("selection", [])

        # Run the potentially long-running CAD operation in a thread pool
        result = await asyncio.to_thread(CAD_ENGINE.execute_command, command, params, selection)

        return create_structured_response(
            result.get("status", "error"),
            command,
            result.get("message", "An unknown error occurred."),
            result.get("data"),
            result.get("object_ids")
        )

    except Exception as e:
        app.logger.error(f"Command execution failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "command", str(e)), 500)

@app.route('/api/tessellate', methods=['POST'])
async def api_tessellate():
    """Generates and returns the tessellated geometry for the viewport."""
    try:
        # Tessellation can be CPU intensive, run in a thread
        tessellation_data = await asyncio.to_thread(CAD_ENGINE.get_tessellation)
        return create_structured_response("success", "tessellate", "Tessellation complete.", data=tessellation_data)
    except Exception as e:
        app.logger.error(f"Tessellation failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "tessellate", str(e)), 500)

@app.route('/api/import', methods=['POST'])
async def api_import():
    """Handles file uploads for import."""
    try:
        files = await request.files
        if 'file' not in files:
            return await make_response(create_structured_response("error", "import", "No file part in request."), 400)

        file = files['file']
        if file.filename == '':
            return await make_response(create_structured_response("error", "import", "No file selected."), 400)

        # Use a unique name to avoid collisions, but keep original for extension
        filename = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        await file.save(filepath)

        # Run import in a thread
        result = await asyncio.to_thread(CAD_ENGINE.import_file, filepath, file.filename)
        
        # Clean up uploaded file
        os.remove(filepath)

        return create_structured_response(
            result.get("status", "error"),
            "import",
            result.get("message", "An unknown error occurred."),
            result.get("data"),
            result.get("object_ids")
        )

    except Exception as e:
        app.logger.error(f"Import failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "import", str(e)), 500)

@app.route('/api/export', methods=['POST'])
async def api_export():
    """Exports the current document to a specified format."""
    try:
        payload = await request.get_json()
        file_format = payload.get("format", "step").lower()
        
        # Run export in a thread
        result = await asyncio.to_thread(CAD_ENGINE.export_file, file_format)

        if result["status"] != "success":
            return await make_response(create_structured_response(
                result["status"], "export", result["message"]
            ), 400)

        file_data = result["data"]["file_content"]
        filename = result["data"]["filename"]

        response = await make_response(file_data)
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/octet-stream'
        return response

    except Exception as e:
        app.logger.error(f"Export failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "export", str(e)), 500)

@app.route('/api/document/new', methods=['POST'])
async def api_new_document():
    """Clears the current document and starts a new one."""
    try:
        await asyncio.to_thread(CAD_ENGINE.new_document)
        return create_structured_response("success", "new_document", "New document created.")
    except Exception as e:
        app.logger.error(f"New document creation failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "new_document", str(e)), 500)

@app.route('/api/assistant', methods=['POST'])
async def api_assistant():
    """Handles natural language commands from the Engineering Assistant."""
    try:
        payload = await request.get_json()
        prompt = payload.get("prompt")
        if not prompt:
            return await make_response(create_structured_response("error", "assistant", "Empty prompt received."), 400)

        # The assistant logic is now part of the main engine
        result = await asyncio.to_thread(CAD_ENGINE.execute_assistant_command, prompt)

        return create_structured_response(
            result.get("status", "error"),
            "assistant",
            result.get("message", "An unknown error occurred."),
            result.get("data"),
            result.get("object_ids")
        )
    except Exception as e:
        app.logger.error(f"Assistant command failed: {e}", exc_info=True)
        return await make_response(create_structured_response("error", "assistant", str(e)), 500)


# --- Static Content ---

@app.route('/')
async def index():
    """Serves the main application page."""
    return await send_from_directory('templates', 'index.html')

@app.route('/<path:path>')
async def send_static(path):
    """Serves static files from the 'static' directory."""
    return await send_from_directory('static', path)

# --- Main Execution ---
if __name__ == '__main__':
    # For production, use a real ASGI server like Hypercorn
    # hypercorn app:app -b 0.0.0.0:5001
    app.run(host='0.0.0.0', port=5001, debug=True)