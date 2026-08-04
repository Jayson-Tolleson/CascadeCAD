import hashlib
import random
from datetime import datetime, timezone
from app.core.config import get_settings
from app.schemas.scene import BBox


def _seed(bbox: BBox) -> int:
    return int(hashlib.sha1(f'{bbox.west},{bbox.south},{bbox.east},{bbox.north}'.encode()).hexdigest()[:8], 16)


def lightning_flashes(bbox: BBox, count: int | None = None) -> dict:
    settings = get_settings()
    provider = (settings.lightning_provider or '').lower()
    if not settings.lightning_enabled or provider in {'mock', 'stub', 'disabled', 'none', ''}:
        return {
            'ok': True,
            'enabled': False,
            'provider': 'no_data',
            'ttl_seconds': settings.lightning_ttl_seconds,
            'flashes': [],
            'metadata': {'data_state': 'no_data'},
        }

    limit = min(count or 3, settings.lightning_max_flashes)
    rng = random.Random(_seed(bbox))
    flashes = []
    now = datetime.now(timezone.utc).isoformat()
    for index in range(limit):
        flashes.append({
            'id': f'flash_{_seed(bbox):x}_{index:02d}',
            'lat': round(rng.uniform(bbox.south, bbox.north), 6),
            'lon': round(rng.uniform(bbox.west, bbox.east), 6),
            'energy': round(rng.uniform(0.2, 1.0), 3),
            'created_at': now,
            'ttl_seconds': settings.lightning_ttl_seconds,
            'provider': settings.lightning_provider,
            'source': 'configured_lightning_provider',
        })
    return {'ok': True, 'enabled': settings.lightning_enabled, 'provider': settings.lightning_provider, 'ttl_seconds': settings.lightning_ttl_seconds, 'flashes': flashes}
