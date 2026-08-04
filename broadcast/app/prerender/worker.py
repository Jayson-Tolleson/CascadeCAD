from __future__ import annotations

from typing import Any

from app.prerender.cache import get_render_cache
from app.schemas.scene import BBox
from app.services.field_truth_engine import get_field_truth_engine


def precompute_viewport_render_features(bbox: BBox, tier: str = "regional") -> dict[str, Any]:
    """Compute cloud/ocean feature patches and write feature recipes to PostGIS.

    This is the first pre-render worker shape.  It can be called manually from scripts
    today; later it can run on a schedule per stable tile/cycle.  The runtime stream can
    read these stored features when available and fall back to live field extraction when
    empty.
    """

    engine = get_field_truth_engine()
    cache = get_render_cache()
    cloud_payload, cloud_status = engine.cloud_features_patch(bbox, tier=tier, use_render_cache=False)
    ocean_payload, ocean_status = engine.ocean_features_patch(bbox, tier=tier, use_render_cache=False)
    cloud_write = cache.write_cloud(cloud_payload)
    ocean_write = cache.write_ocean(ocean_payload)
    return {
        "ok": True,
        "bbox": bbox.model_dump(mode="json"),
        "tier": tier,
        "render_cache": cache.status(),
        "clouds": {
            "status": cloud_status.model_dump(mode="json"),
            "feature_count": cloud_payload.get("feature_count"),
            "families": cloud_payload.get("families"),
            "write": cloud_write,
        },
        "ocean": {
            "status": ocean_status.model_dump(mode="json"),
            "current_vectors": ocean_payload.get("current_vector_count"),
            "bait_clusters": ocean_payload.get("bait_cluster_count"),
            "write": ocean_write,
        },
    }


def precompute_cloud_render_features(bbox: BBox, tier: str = "regional") -> dict[str, Any]:
    """Compute only the Clouds pill feature patch and write it to PostGIS.

    This is the pill-by-pill path for /gfs: Clouds can be rebuilt, tested, and
    cached independently before moving on to rain/bait/boats/inland-water.
    """

    engine = get_field_truth_engine()
    cache = get_render_cache()
    cloud_payload, cloud_status = engine.cloud_features_patch(bbox, tier=tier, use_render_cache=False)
    cloud_write = cache.write_cloud(cloud_payload)
    return {
        "ok": True,
        "layer": "clouds",
        "bbox": bbox.model_dump(mode="json"),
        "tier": tier,
        "render_cache": cache.status(),
        "clouds": {
            "status": cloud_status.model_dump(mode="json"),
            "feature_count": cloud_payload.get("feature_count"),
            "families": cloud_payload.get("families"),
            "source": cloud_payload.get("source"),
            "write": cloud_write,
        },
    }
