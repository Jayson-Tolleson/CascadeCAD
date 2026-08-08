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
    for category, values in caps.items():
        print(f"  {category.title()}:")
        if isinstance(values, dict):
            for k, v in values.items():
                print(f"    - {k}: {'Yes' if v else 'No'}")
        elif isinstance(values, list):
            print(f"    - {', '.join(values)}")
    print("---------------------------")
    return engine_instance