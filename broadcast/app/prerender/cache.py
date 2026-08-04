from __future__ import annotations

from typing import Any

from app.prerender.postgis_repository import PostGISRenderFeatureRepository
from app.schemas.scene import BBox


def get_render_repository() -> PostGISRenderFeatureRepository:
    return PostGISRenderFeatureRepository()


class RenderCache:
    def __init__(self) -> None:
        self.repo = get_render_repository()

    def status(self) -> dict[str, Any]:
        return self.repo.status()

    def cloud_hit(self, bbox: BBox, tier: str) -> dict[str, Any] | None:
        return self.repo.cloud_features_patch(bbox, tier=tier)

    def ocean_hit(self, bbox: BBox, tier: str) -> dict[str, Any] | None:
        return self.repo.ocean_features_patch(bbox, tier=tier)

    def write_cloud(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.repo.upsert_cloud_patch(payload)

    def write_ocean(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.repo.upsert_ocean_patch(payload)


def get_render_cache() -> RenderCache:
    return RenderCache()
