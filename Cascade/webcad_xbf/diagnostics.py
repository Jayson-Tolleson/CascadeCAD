"""
CascadeCAD Engineering Diagnostic Logger
Symbol-based debug stream.
"""

CAD_SYMBOLS = {
    "system": "Σ",
    "command": "λ",
    "geometry": "Γ",
    "transform": "Δ",
    "mesh": "△",
    "math": "√",
    "stream": "∞",
    "complete": "Ω",
    "warning": "⚠",
    "error": "✖",
}


def cadlog(kind, message):
    """
    Generate a CascadeCAD engineering log message.
    """
    symbol = CAD_SYMBOLS.get(kind, "•")
    return f"{symbol} {message}"


def cad_event(kind, message):
    """
    Print diagnostic event.
    """
    line = cadlog(kind, message)
    print(line, flush=True)
    return line
