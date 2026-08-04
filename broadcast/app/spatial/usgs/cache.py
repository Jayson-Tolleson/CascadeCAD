import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from app.core.config import get_settings
from app.schemas.scene import BBox


def bbox_hash(bbox: BBox) -> str:
    return hashlib.sha1(f'{bbox.west},{bbox.south},{bbox.east},{bbox.north}'.encode()).hexdigest()[:12]


def batch_id(source_family: str, bbox: BBox) -> str:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return f'{source_family}_{bbox_hash(bbox)}_{stamp}'


class USGSIngestCache:
    def __init__(self) -> None:
        root = Path(get_settings().usgs_cache_dir)
        self.raw = root / 'raw'
        self.normalized = root / 'normalized'
        self.diagnostics = root / 'diagnostics'
        for path in [self.raw, self.normalized, self.diagnostics]:
            path.mkdir(parents=True, exist_ok=True)

    def write_json(self, folder: str, name: str, payload: dict | list) -> Path:
        target_dir = {'raw': self.raw, 'normalized': self.normalized, 'diagnostics': self.diagnostics}[folder]
        path = target_dir / f'{name}.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path
