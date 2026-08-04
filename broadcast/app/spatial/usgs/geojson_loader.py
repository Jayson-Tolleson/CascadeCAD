import json
from pathlib import Path


def load_geojson(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))
