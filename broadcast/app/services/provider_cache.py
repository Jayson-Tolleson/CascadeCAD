import json
import os
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    # app/services/provider_cache.py -> project root is two parents up from app/.
    return Path(__file__).resolve().parents[2]


class ProviderCache:
    def __init__(self, cache_dir: str) -> None:
        raw = Path(cache_dir or ".cache/provider")
        if raw.is_absolute():
            self.cache_dir = raw
        else:
            base = Path(os.environ.get("LFTR_CACHE_ROOT", "")).expanduser() if os.environ.get("LFTR_CACHE_ROOT") else _project_root()
            self.cache_dir = base / raw
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        safe = ''.join(char if char.isalnum() or char in '-_' else '_' for char in key)
        return self.cache_dir / f'{safe}.json'

    def load(self, key: str) -> dict[str, Any] | None:
        path = self.path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding='utf-8'))

    def save(self, key: str, payload: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path_for(key).write_text(json.dumps(payload), encoding='utf-8')
