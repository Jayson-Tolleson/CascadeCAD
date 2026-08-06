import json
from typing import Dict, List, Any, Type

class Command:
    """Base class for all executable actions in CascadeCAD."""
    def __init__(self, **kwargs):
        self.params = kwargs

    def execute(self, model_context) -> bool:
        raise NotImplementedError

    def undo(self, model_context) -> bool:
        raise NotImplementedError
        
    def to_dict(self):
        return {"command": self.__class__.__name__, "params": self.params}


class MacroRecorder:
    def __init__(self):
        self.is_recording = False
        self.macro_steps = []

    def start(self):
        self.is_recording = True
        self.macro_steps = []
        print("[Macro] Recording started.")

    def record(self, command: Command):
        if self.is_recording:
            self.macro_steps.append(command.to_dict())

    def stop_and_save(self, filepath: str):
        self.is_recording = False
        with open(filepath, 'w') as f:
            json.dump(self.macro_steps, f, indent=2)
        print(f"[Macro] Saved {len(self.macro_steps)} steps to {filepath}.")


class CommandDispatcher:
    """Central hub for executing commands, managing history, and routing to plugins."""
    
    def __init__(self, model_context):
        self.context = model_context
        self.registry: Dict[str, Type[Command]] = {}
        
        # Undo/Redo Stacks
        self.history: List[Command] = []
        self.redo_stack: List[Command] = []
        
        self.recorder = MacroRecorder()

    def register_command(self, name: str, command_class: Type[Command]):
        """Plugin API: Allows external modules to inject new commands."""
        self.registry[name] = command_class
        print(f"[Dispatcher] Registered command: {name}")

    def execute(self, command_name: str, **kwargs) -> bool:
        if command_name not in self.registry:
            print(f"[Error] Command '{command_name}' not found.")
            return False
            
        cmd_instance = self.registry[command_name](**kwargs)
        
        try:
            success = cmd_instance.execute(self.context)
            if success:
                self.history.append(cmd_instance)
                self.redo_stack.clear()  # Clear redo on new action
                self.recorder.record(cmd_instance)
                return True
        except Exception as e:
            print(f"[Error] Command execution failed: {e}")
            
        return False

    def undo(self):
        if not self.history:
            return False
        cmd = self.history.pop()
        cmd.undo(self.context)
        self.redo_stack.append(cmd)
        print(f"[Dispatcher] Undid {cmd.__class__.__name__}")
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute(self.context)
        self.history.append(cmd)
        print(f"[Dispatcher] Redid {cmd.__class__.__name__}")
        return True


class CascadePythonAPI:
    """Python API wrapper for headless scripting and automation."""
    def __init__(self, dispatcher: CommandDispatcher):
        self.dispatcher = dispatcher

    def run_script(self, script_string: str):
        """Executes a block of Python code using the API namespace."""
        namespace = {
            "execute": self.dispatcher.execute,
            "undo": self.dispatcher.undo,
            "redo": self.dispatcher.redo,
            "macro_start": self.dispatcher.recorder.start,
        }
        exec(script_string, namespace)
