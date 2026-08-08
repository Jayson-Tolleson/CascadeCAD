# MagicXBF Engine Package
# This file initializes the engine and serves as the public facade.

from .main import Engine

__all__ = ['initialize']

def initialize() -> Engine:
    """
    Initializes and returns a single instance of the MagicXBF Engine.
    This function is called once by the main application server.
    """
    print("Initializing MagicXBF CAD Engine...")
    engine_instance = Engine()
    print("Engine initialization complete.")
    caps = engine_instance.get_capabilities()
    print("--- Engine Capabilities ---")
    print(f"  B-Rep Kernel: {caps['kernels']['brep_kernel']}")
    print(f"  Mesh Kernel: {caps['kernels']['mesh_kernel']}")
    print(f"  Import Formats: {', '.join(caps['import_formats'])}")
    print(f"  Export Formats: {', '.join(caps['export_formats'])}")
    print(f"  Primitives: {', '.join(caps['primitives'])}")
    print("---------------------------")
    return engine_instance