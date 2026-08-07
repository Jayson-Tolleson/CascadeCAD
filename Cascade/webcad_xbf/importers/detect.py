from pathlib import Path
from .formats import get_format


def detect_file(filename):

    info = get_format(filename)

    return {
        "filename": filename,
        "extension": info["extension"],
        "category": info["category"],
        "handler": info["handler"],
        "supported": info["handler"] is not None
    }


if __name__ == "__main__":
    import sys

    for filename in sys.argv[1:]:
        print(detect_file(filename))
