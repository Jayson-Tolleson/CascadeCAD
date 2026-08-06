import json
import os
import vertexai
from vertexai.generative_models import GenerativeModel, Part

class EngineeringAssistant:
    """
    LLM-powered Engineering Assistant bridging natural language to the Command Platform.
    Designed to integrate with Vertex AI (Gemini) to output deterministic JSON commands, 
    Python scripts, and engineering analysis.
    """
    
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
        self.location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        # Initialize Vertex AI
        vertexai.init(project=self.project_id, location=self.location)
        self.model = GenerativeModel("gemini-1.5-pro-preview-0409")
        print("[Assistant] Vertex AI Interface Initialized.")

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Mock LLM call. Replace with actual Vertex AI generation."""
        response = self.model.generate_content([system_prompt, user_prompt])
        return response.text
        
        # Mocking the Vertex AI response based on intent for the foundation patch
        if "draw a cube" in user_prompt.lower():
            return json.dumps([{"command": "CreateCube", "params": {"height": 6000, "rot_y": 45}}])
        elif "hide all bolts" in user_prompt.lower():
            return json.dumps([{"command": "HideHardware", "params": {"type": "bolt"}}])
        elif "python" in user_prompt.lower() or "script" in user_prompt.lower():
            return "execute('CreateCube', size=10)\nexecute('Fillet', radius=2)"
        
        return json.dumps([{"command": "Unknown", "params": {}}])

    def process_natural_language(self, query: str) -> dict:
        """Translates plain text into a sequence of executable commands."""
        system_prompt = (
            "You are an engineering CAD assistant. Map the user's request to valid "
            "CascadeCAD commands. Output ONLY a JSON array of command objects with 'command' "
            "and 'params' keys."
        )
        
        response_text = self._call_llm(system_prompt, query)
        
        try:
            commands = json.loads(response_text)
            executed = []
            for cmd_data in commands:
                cmd_name = cmd_data.get("command")
                params = cmd_data.get("params", {})
                
                # Route to the dispatcher from Patch E
                success = self.dispatcher.execute(cmd_name, **params)
                if success:
                    executed.append(cmd_name)
                    
            return {"status": "success", "commands_executed": executed}
        except json.JSONDecodeError:
            return {"status": "error", "message": "LLM failed to output valid command JSON."}

    def generate_python_script(self, intent: str) -> str:
        """Generates a CascadePythonAPI compatible script from an engineering intent."""
        system_prompt = "Output only valid Python code using the execute(cmd, **kwargs) API."
        return self._call_llm(system_prompt, intent)

    def analyze_model(self, metrics: dict) -> dict:
        """Feeds model stats (Milestone 6) into Vertex AI to get engineering recommendations."""
        prompt = f"Analyze these CAD metrics and suggest optimizations: {json.dumps(metrics)}"
        # Mock response parsing
        return {
            "insights": "High triangle count detected in fastener sub-assemblies.",
            "recommendations": [
                {"action": "Instance Hardware", "command": "InstanceHardware"},
                {"action": "Suppress Cosmetic Fillets", "command": "SuppressFeatures", "params": {"type": "fillet"}}
            ]
        }
