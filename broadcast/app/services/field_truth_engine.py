from app.core.config import get_settings
from app.fields.base import FieldPatch
from app.fields.encoders import encode_atmosphere_json_patch, encode_ocean_json_patch
from app.fields.tiles import tile_id_for_bbox
from app.providers.gfs_ncss import get_gfs_provider
from app.providers.provider_status import ProviderStatus
from app.providers.rtofs_ncep import get_rtofs_provider
from app.schemas.scene import BBox
from app.services.cloud_features import extract_cloud_features
from app.services.ocean_features import extract_ocean_features
from app.services.ocean_truth_engine import get_ocean_truth_engine
from app.prerender.cache import get_render_cache


def _public_provider_status(status: ProviderStatus) -> dict:
    """Small stream-safe provider summary.

    No truth-guard language and no mock/stub render promotion.  Providers now either
    return live/last-good parsed data or honest no-data frames.
    """
    return {
        "provider": status.provider,
        "mode": status.mode,
        "enabled": status.enabled,
        "live_ok": bool(status.live_ok),
        "cache_hit": bool(status.cache_hit),
        "valid_time": status.valid_time,
        "generated_time": status.generated_time,
        "data_state": "live_or_last_good" if status.live_ok else "no_data",
        "diagnostics": "see /gfs/api/providers/status or /gfs/api/field-truth?debug_raw=true",
    }


def _feature_source_kind(status: ProviderStatus) -> str:
    return "live_provider" if status.live_ok else "no_data"


class FieldTruthEngine:
    def atmosphere_frame(self, bbox: BBox):
        return get_gfs_provider().fetch_atmosphere(bbox)

    def atmosphere_patch(self, bbox: BBox, lod: int = 0) -> tuple[FieldPatch, ProviderStatus]:
        frame, status = self.atmosphere_frame(bbox)
        patch = encode_atmosphere_json_patch(frame, lod=lod)
        patch.payload["provider"] = status.model_dump(mode="json")
        patch.payload["metadata"] = frame.metadata
        return patch, status

    def atmosphere_stream_patch(self, bbox: BBox, lod: int = 0, debug_raw: bool = False) -> tuple[FieldPatch, ProviderStatus]:
        frame, status = self.atmosphere_frame(bbox)
        patch = encode_atmosphere_json_patch(frame, lod=lod)
        patch.payload["provider"] = status.model_dump(mode="json") if debug_raw else _public_provider_status(status)
        patch.payload["metadata"] = frame.metadata if debug_raw else {
            **{k: v for k, v in frame.metadata.items() if k not in {"source_url", "error"}},
            "source_kind": _feature_source_kind(status),
        }
        return patch, status

    def cloud_features_patch(
        self,
        bbox: BBox,
        lod: int = 0,
        tier: str = "regional",
        use_render_cache: bool = True,
        debug_raw: bool = False,
    ) -> tuple[dict, ProviderStatus]:
        settings = get_settings()
        cache = get_render_cache()
        postgis_cache_error: str | None = None
        if use_render_cache and settings.render_cache_enabled and settings.render_cache_prefer_postgis:
            try:
                cached = cache.cloud_hit(bbox, tier=tier)
            except Exception as exc:
                cached = None
                postgis_cache_error = str(exc)
            if cached and cached.get("feature_count", 0) > 0:
                provider_status = get_gfs_provider().status()
                cached.update({
                    "event_type": "cloud.features.patch",
                    "patch_id": f"cloud-features-postgis-{cached.get('valid_time', 'latest')}",
                    "tile_id": f"cloud-features:{bbox.west:.2f},{bbox.south:.2f},{bbox.east:.2f},{bbox.north:.2f}",
                    "lod": lod,
                    "tier": tier,
                    "provider": provider_status.model_dump(mode="json") if debug_raw else _public_provider_status(provider_status),
                    "metadata": {
                        **cached.get("metadata", {}),
                        "render_cache": "postgis_hit",
                        "source_kind": "live_provider",
                        "pill": "clouds",
                    },
                })
                return cached, provider_status

        frame, status = self.atmosphere_frame(bbox)
        payload = extract_cloud_features(
            frame,
            threshold=settings.cloud_feature_threshold,
            max_features=settings.cloud_feature_max_features,
        )
        payload.update({
            "event_type": "cloud.features.patch",
            "patch_id": f"cloud-features-{payload['valid_time']}",
            "tile_id": f"cloud-features:{bbox.west:.2f},{bbox.south:.2f},{bbox.east:.2f},{bbox.north:.2f}",
            "lod": lod,
            "tier": tier,
            "provider": status.model_dump(mode="json") if debug_raw else _public_provider_status(status),
            "metadata": {
                **(frame.metadata if debug_raw else {k: v for k, v in frame.metadata.items() if k not in {"source_url", "error"}}),
                **payload.get("metadata", {}),
                "field_engine": frame.metadata.get("field_engine", "bounded_gfs_ncss_netcdf_parser"),
                "grid_shape": payload["grid_shape"],
                "feature_extractor": "family_grouped_connected_components_threshold",
                "render_contract": "frontend renders meteorological cloud families from real/last-good provider feature recipes",
                "render_cache": "miss_live_generated" if settings.render_cache_enabled and status.live_ok else "disabled_or_no_data",
                "postgis_cache_error": postgis_cache_error,
                "source_kind": _feature_source_kind(status),
                "pill": "clouds",
            },
        })
        if status.live_ok and use_render_cache and settings.render_cache_enabled and settings.render_cache_write_through:
            try:
                payload["metadata"]["render_cache_write"] = cache.write_cloud(payload)
            except Exception as exc:
                payload["metadata"]["render_cache_write"] = {"ok": False, "error": str(exc), "layer": "clouds"}
        return payload, status

    def ocean_patch(self, bbox: BBox, lod: int = 0) -> tuple[FieldPatch, ProviderStatus]:
        return get_ocean_truth_engine().ocean_patch(bbox, lod=lod)

    def ocean_stream_patch(self, bbox: BBox, lod: int = 0, debug_raw: bool = False) -> tuple[FieldPatch, ProviderStatus]:
        frame, status = get_ocean_truth_engine().ocean_frame(bbox)
        patch = encode_ocean_json_patch(frame, lod=lod)
        patch.payload["provider"] = status.model_dump(mode="json") if debug_raw else _public_provider_status(status)
        patch.payload["metadata"] = frame.metadata if debug_raw else {
            **{k: v for k, v in frame.metadata.items() if k not in {"source_url", "error"}},
            "source_kind": _feature_source_kind(status),
        }
        return patch, status

    def ocean_features_patch(
        self,
        bbox: BBox,
        lod: int = 0,
        tier: str = "regional",
        use_render_cache: bool = True,
        debug_raw: bool = False,
    ) -> tuple[dict, ProviderStatus]:
        settings = get_settings()
        cache = get_render_cache()
        postgis_cache_error: str | None = None
        if use_render_cache and settings.render_cache_enabled and settings.render_cache_prefer_postgis:
            try:
                cached = cache.ocean_hit(bbox, tier=tier)
            except Exception as exc:
                cached = None
                postgis_cache_error = str(exc)
            if cached and (cached.get("current_vector_count", 0) or cached.get("bait_cluster_count", 0)):
                provider_status = get_rtofs_provider().status()
                cached.update({
                    "event_type": "ocean.features.patch",
                    "patch_id": f"ocean-features-postgis-{cached.get('valid_time', 'latest')}",
                    "tile_id": f"ocean-features:{bbox.west:.2f},{bbox.south:.2f},{bbox.east:.2f},{bbox.north:.2f}",
                    "lod": lod,
                    "tier": tier,
                    "provider": provider_status.model_dump(mode="json") if debug_raw else _public_provider_status(provider_status),
                    "metadata": {
                        **cached.get("metadata", {}),
                        "render_cache": "postgis_hit",
                        "source_kind": "live_provider",
                        "pill": "ocean",
                    },
                })
                return cached, provider_status

        frame, status = get_ocean_truth_engine().ocean_frame(bbox)
        payload = extract_ocean_features(
            frame,
            max_current_vectors=settings.ocean_feature_max_current_vectors,
            bait_threshold=settings.ocean_bait_threshold,
            max_bait_clusters=settings.ocean_feature_max_bait_clusters,
        )
        payload.update({
            "event_type": "ocean.features.patch",
            "patch_id": f"ocean-features-{payload['valid_time']}",
            "tile_id": f"ocean-features:{bbox.west:.2f},{bbox.south:.2f},{bbox.east:.2f},{bbox.north:.2f}",
            "lod": lod,
            "tier": tier,
            "provider": status.model_dump(mode="json") if debug_raw else _public_provider_status(status),
            "metadata": {
                **payload.get("metadata", {}),
                **(frame.metadata if debug_raw else {k: v for k, v in frame.metadata.items() if k not in {"source_url", "error"}}),
                "render_contract": "PostGIS can cache current/bait feature recipes only from real/last-good provider frames",
                "render_cache": "miss_live_generated" if settings.render_cache_enabled and status.live_ok else "disabled_or_no_data",
                "postgis_cache_error": postgis_cache_error,
                "source_kind": _feature_source_kind(status),
                "pill": "ocean",
            },
        })
        if status.live_ok and use_render_cache and settings.render_cache_enabled and settings.render_cache_write_through:
            try:
                payload["metadata"]["render_cache_write"] = cache.write_ocean(payload)
            except Exception as exc:
                payload["metadata"]["render_cache_write"] = {"ok": False, "error": str(exc), "layer": "ocean"}
        return payload, status

    def render_cache_status(self) -> dict:
        return get_render_cache().status()


def get_field_truth_engine() -> FieldTruthEngine:
    return FieldTruthEngine()
