from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from app.core.config import get_settings
from app.db.connect import postgis_connection, safe_postgis_status
from app.schemas.scene import BBox


def bbox_wkt(bbox: BBox) -> str:
    return (
        f"POLYGON(({bbox.west} {bbox.south},{bbox.east} {bbox.south},"
        f"{bbox.east} {bbox.north},{bbox.west} {bbox.north},{bbox.west} {bbox.south}))"
    )


def feature_bbox(feature: dict[str, Any], fallback: BBox) -> dict[str, float]:
    raw = feature.get("bbox") or {}
    centroid = feature.get("centroid") or {}
    lon = float(centroid.get("lon", (fallback.west + fallback.east) / 2))
    lat = float(centroid.get("lat", (fallback.south + fallback.north) / 2))
    pad_lon = max(0.015, abs(fallback.east - fallback.west) / 256)
    pad_lat = max(0.015, abs(fallback.north - fallback.south) / 256)
    west = float(raw.get("west", lon - pad_lon))
    east = float(raw.get("east", lon + pad_lon))
    south = float(raw.get("south", lat - pad_lat))
    north = float(raw.get("north", lat + pad_lat))
    if east <= west:
        east = west + pad_lon * 2
    if north <= south:
        north = south + pad_lat * 2
    return {"west": west, "south": south, "east": east, "north": north}


def bbox_center(raw: dict[str, float]) -> tuple[float, float]:
    return ((float(raw["west"]) + float(raw["east"])) / 2, (float(raw["south"]) + float(raw["north"])) / 2)


class PostGISRenderFeatureRepository:
    """Optional PostGIS pre-render cache for cloud/ocean/bait render features.

    This repository is deliberately defensive: callers can ask for cached features on
    every stream tick.  If PostGIS is disabled or unavailable, it simply reports not
    available and the field engine continues live/no-data feature extraction.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.schema = self.settings.postgis_schema

    def available(self) -> bool:
        status = safe_postgis_status()
        return (
            bool(self.settings.postgis_enabled)
            and bool(self.settings.render_cache_enabled)
            and bool(status["configured"])
            and bool(status["driver_available"])
        )

    def status(self) -> dict[str, Any]:
        status = safe_postgis_status()
        status.update(
            {
                "enabled": self.settings.render_cache_enabled,
                "prefer_postgis": self.settings.render_cache_prefer_postgis,
                "write_through": self.settings.render_cache_write_through,
                "allow_degraded": self.settings.render_cache_allow_degraded,
                "ttl_seconds": self.settings.render_cache_ttl_seconds,
                "schema": self.schema,
                "cloud_table": f"{self.schema}.cloud_render_features",
                "ocean_table": f"{self.schema}.ocean_render_features",
                "bait_table": f"{self.schema}.bait_render_features",
                "render_tiles_table": f"{self.schema}.render_tiles",
                "available": self.available(),
                "contract": "PostGIS stores feature recipes/geometry; frontend still creates particles from recipe + seed.",
            }
        )
        return status

    def cloud_features_patch(self, bbox: BBox, tier: str = "regional", limit: int | None = None) -> dict[str, Any] | None:
        if not self.available():
            return None
        sql = f"""
            SELECT stable_id, family, render_style, size, density, opacity, altitude_m, thickness_m,
                   wind_u, wind_v, rain_factor, particle_seed, particle_budget, properties,
                   ST_AsGeoJSON(ST_Envelope(geom)) AS bbox_geojson,
                   ST_X(label_point) AS lon, ST_Y(label_point) AS lat,
                   valid_time
            FROM {self.schema}.cloud_render_features
            WHERE geom && ST_GeomFromText(%s, 4326)
              AND ST_Intersects(geom, ST_GeomFromText(%s, 4326))
              AND valid_time >= now() - (%s * interval '1 second')
              AND (%s OR COALESCE(properties->>'_lftr_source_kind', '') = 'live_provider')
            ORDER BY valid_time DESC, density DESC, area_km2 DESC
            LIMIT %s
        """
        result_limit = limit or self.settings.render_cache_max_features
        try:
            with postgis_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, (bbox_wkt(bbox), bbox_wkt(bbox), self.settings.render_cache_ttl_seconds, self.settings.render_cache_allow_degraded, result_limit))
                    rows = cursor.fetchall()
        except Exception:
            return None
        if not rows:
            return None
        features = [self._cloud_row(row) for row in rows]
        return {
            "ok": True,
            "source": "postgis_prerender_cloud_features",
            "valid_time": str(rows[0][17]),
            "bbox": bbox.model_dump(mode="json"),
            "grid_shape": [0, 0],
            "threshold": None,
            "feature_count": len(features),
            "families": sorted({feature["family"] for feature in features}),
            "sizes": sorted({feature.get("size", "unknown") for feature in features}),
            "features": features,
            "metadata": {
                "render_cache": "postgis_hit",
                "feature_store": "cloud_render_features",
                "tier": tier,
                "query_bbox": bbox.model_dump(mode="json"),
                "particle_contract": "frontend generates ellipsoid cloud particles from stable feature recipe + particle_seed",
            },
        }

    def ocean_features_patch(self, bbox: BBox, tier: str = "regional", limit: int | None = None) -> dict[str, Any] | None:
        if not self.available():
            return None
        result_limit = limit or self.settings.render_cache_max_features
        sql = f"""
            SELECT stable_id, feature_type, render_style, depth_min_m, depth_max_m, speed, direction,
                   score, particle_seed, particle_budget, properties,
                   ST_AsGeoJSON(ST_Envelope(geom)) AS bbox_geojson,
                   ST_X(label_point) AS lon, ST_Y(label_point) AS lat,
                   valid_time
            FROM {self.schema}.ocean_render_features
            WHERE geom && ST_GeomFromText(%s, 4326)
              AND ST_Intersects(geom, ST_GeomFromText(%s, 4326))
              AND valid_time >= now() - (%s * interval '1 second')
              AND (%s OR COALESCE(properties->>'_lftr_source_kind', '') = 'live_provider')
            ORDER BY valid_time DESC, score DESC
            LIMIT %s
        """
        try:
            with postgis_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, (bbox_wkt(bbox), bbox_wkt(bbox), self.settings.render_cache_ttl_seconds, self.settings.render_cache_allow_degraded, result_limit))
                    rows = cursor.fetchall()
        except Exception:
            return None
        if not rows:
            return None
        current_vectors: list[dict[str, Any]] = []
        bait_clusters: list[dict[str, Any]] = []
        for row in rows:
            feature = self._ocean_row(row)
            if feature.get("feature_type") == "current_vector":
                current_vectors.append(feature)
            elif feature.get("feature_type") == "bait_cluster":
                bait_clusters.append(feature)
        return {
            "ok": True,
            "source": "postgis_prerender_ocean_features",
            "valid_time": str(rows[0][14]),
            "bbox": bbox.model_dump(mode="json"),
            "grid_shape": [0, 0],
            "depth_levels": [],
            "current_vector_count": len(current_vectors),
            "bait_cluster_count": len(bait_clusters),
            "current_vectors": current_vectors,
            "bait_clusters": bait_clusters,
            "metadata": {
                "render_cache": "postgis_hit",
                "feature_store": "ocean_render_features",
                "tier": tier,
                "query_bbox": bbox.model_dump(mode="json"),
                "feature_count": len(rows),
            },
        }

    def upsert_cloud_patch(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.available():
            return {"ok": True, "skipped": True, "reason": "PostGIS render cache unavailable"}
        source_kind = (payload.get("metadata") or {}).get("source_kind", "unknown")
        if source_kind != "live_provider" and not self.settings.render_cache_allow_degraded:
            return {"ok": True, "skipped": True, "reason": "non_realtime_payload_not_cached", "source_kind": source_kind}
        features = payload.get("features") or []
        bbox = BBox(**payload["bbox"])
        valid_time = payload.get("valid_time") or datetime.now(timezone.utc).isoformat()
        patch_id = payload.get("patch_id") or f"cloud-patch-{valid_time}"
        tile_id = payload.get("tile_id") or "cloud-features:unknown"
        sql = f"""
            INSERT INTO {self.schema}.cloud_render_features
                (stable_id, patch_id, tile_id, valid_time, family, render_style, size, density, opacity,
                 altitude_m, thickness_m, wind_u, wind_v, rain_factor, particle_seed, particle_budget,
                 area_cells, area_km2, properties, geom, label_point, bbox, updated_at)
            VALUES
                (%s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s::jsonb, ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                 ST_MakeEnvelope(%s, %s, %s, %s, 4326), now())
            ON CONFLICT (stable_id) DO UPDATE SET
                patch_id = EXCLUDED.patch_id, tile_id = EXCLUDED.tile_id, valid_time = EXCLUDED.valid_time,
                family = EXCLUDED.family, render_style = EXCLUDED.render_style, size = EXCLUDED.size,
                density = EXCLUDED.density, opacity = EXCLUDED.opacity, altitude_m = EXCLUDED.altitude_m,
                thickness_m = EXCLUDED.thickness_m, wind_u = EXCLUDED.wind_u, wind_v = EXCLUDED.wind_v,
                rain_factor = EXCLUDED.rain_factor, particle_seed = EXCLUDED.particle_seed,
                particle_budget = EXCLUDED.particle_budget, area_cells = EXCLUDED.area_cells,
                area_km2 = EXCLUDED.area_km2, properties = EXCLUDED.properties, geom = EXCLUDED.geom,
                label_point = EXCLUDED.label_point, bbox = EXCLUDED.bbox, updated_at = now()
        """
        try:
            with postgis_connection() as connection:
                with connection.cursor() as cursor:
                    for feature in features:
                        fb = feature_bbox(feature, bbox)
                        lon, lat = bbox_center(fb)
                        props = dict(feature)
                        props["_lftr_source_kind"] = (payload.get("metadata") or {}).get("source_kind", "unknown")
                        props["_lftr_source_policy"] = "live_provider_only_by_default"
                        props["_lftr_pill"] = "clouds"
                        seed = str(feature.get("particle_seed") or feature.get("id") or f"cloud-{lon:.3f}-{lat:.3f}")
                        stable_id = str(feature.get("id") or seed)
                        budget = int(feature.get("particle_budget") or self._cloud_particle_budget(feature))
                        area_cells = int(feature.get("area_cells") or 0)
                        area_km2 = float(feature.get("area_km2") or max(0.0, (fb["east"] - fb["west"]) * (fb["north"] - fb["south"]) * 111.0 * 111.0))
                        cursor.execute(
                            sql,
                            (
                                stable_id, patch_id, tile_id, valid_time, feature.get("family", "unknown"),
                                feature.get("render_style", "unknown"), feature.get("size", "medium"),
                                float(feature.get("density") or 0.0), float(feature.get("opacity") or 0.35),
                                float(feature.get("altitude_m") or 0.0), float(feature.get("thickness_m") or 0.0),
                                float(feature.get("wind_u") or 0.0), float(feature.get("wind_v") or 0.0),
                                float(feature.get("rain_rate") or feature.get("rain_factor") or 0.0), seed, budget,
                                area_cells, area_km2, json.dumps(props),
                                fb["west"], fb["south"], fb["east"], fb["north"], lon, lat,
                                fb["west"], fb["south"], fb["east"], fb["north"],
                            ),
                        )
            self.upsert_render_tile(payload, layer="clouds", feature_count=len(features))
            return {"ok": True, "skipped": False, "stored": len(features), "layer": "clouds"}
        except Exception as exc:
            return {"ok": False, "skipped": True, "layer": "clouds", "error": str(exc)}

    def upsert_ocean_patch(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.available():
            return {"ok": True, "skipped": True, "reason": "PostGIS render cache unavailable"}
        source_kind = (payload.get("metadata") or {}).get("source_kind", "unknown")
        if source_kind != "live_provider" and not self.settings.render_cache_allow_degraded:
            return {"ok": True, "skipped": True, "reason": "non_realtime_payload_not_cached", "source_kind": source_kind}
        bbox = BBox(**payload["bbox"])
        valid_time = payload.get("valid_time") or datetime.now(timezone.utc).isoformat()
        patch_id = payload.get("patch_id") or f"ocean-patch-{valid_time}"
        tile_id = payload.get("tile_id") or "ocean-features:unknown"
        rows: list[tuple[str, dict[str, Any]]] = []
        rows.extend(("current_vector", item) for item in payload.get("current_vectors") or [])
        rows.extend(("bait_cluster", item) for item in payload.get("bait_clusters") or [])
        sql = f"""
            INSERT INTO {self.schema}.ocean_render_features
                (stable_id, patch_id, tile_id, valid_time, feature_type, render_style, depth_min_m, depth_max_m,
                 speed, direction, score, particle_seed, particle_budget, properties, geom, label_point, bbox, updated_at)
            VALUES
                (%s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                 ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                 ST_MakeEnvelope(%s, %s, %s, %s, 4326), now())
            ON CONFLICT (stable_id) DO UPDATE SET
                patch_id = EXCLUDED.patch_id, tile_id = EXCLUDED.tile_id, valid_time = EXCLUDED.valid_time,
                feature_type = EXCLUDED.feature_type, render_style = EXCLUDED.render_style,
                depth_min_m = EXCLUDED.depth_min_m, depth_max_m = EXCLUDED.depth_max_m,
                speed = EXCLUDED.speed, direction = EXCLUDED.direction, score = EXCLUDED.score,
                particle_seed = EXCLUDED.particle_seed, particle_budget = EXCLUDED.particle_budget,
                properties = EXCLUDED.properties, geom = EXCLUDED.geom, label_point = EXCLUDED.label_point,
                bbox = EXCLUDED.bbox, updated_at = now()
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                for feature_type, feature in rows:
                    fb = feature_bbox(feature, bbox)
                    lon = float(feature.get("lon") or (feature.get("centroid") or {}).get("lon") or bbox_center(fb)[0])
                    lat = float(feature.get("lat") or (feature.get("centroid") or {}).get("lat") or bbox_center(fb)[1])
                    pad = 0.02 if feature_type == "current_vector" else max(0.02, max(fb["east"] - fb["west"], fb["north"] - fb["south"]) / 2)
                    if feature_type == "current_vector":
                        fb = {"west": lon - pad, "south": lat - pad, "east": lon + pad, "north": lat + pad}
                    props = dict(feature)
                    props["_lftr_source_kind"] = (payload.get("metadata") or {}).get("source_kind", "unknown")
                    props["_lftr_source_policy"] = "live_provider_only_by_default"
                    stable_id = str(feature.get("id") or f"{feature_type}-{lon:.4f}-{lat:.4f}")
                    seed = str(feature.get("particle_seed") or stable_id)
                    score = float(feature.get("score") or feature.get("speed") or 0.0)
                    cursor.execute(
                        sql,
                        (
                            stable_id, patch_id, tile_id, valid_time, feature_type,
                            feature.get("render_style") or feature.get("render_hint") or feature_type,
                            float(feature.get("depth_min_m") or feature.get("depth_m") or 0.0),
                            float(feature.get("depth_max_m") or feature.get("depth_m") or 0.0),
                            float(feature.get("speed") or 0.0), float(feature.get("direction") or 0.0),
                            score, seed, int(feature.get("particle_budget") or (48 if feature_type == "bait_cluster" else 12)), json.dumps(props),
                            fb["west"], fb["south"], fb["east"], fb["north"], lon, lat,
                            fb["west"], fb["south"], fb["east"], fb["north"],
                        ),
                    )
        self.upsert_render_tile(payload, layer="ocean", feature_count=len(rows))
        return {"ok": True, "skipped": False, "stored": len(rows), "layer": "ocean"}

    def upsert_render_tile(self, payload: dict[str, Any], layer: str, feature_count: int) -> None:
        if not self.available():
            return
        bbox = BBox(**payload["bbox"])
        patch_id = payload.get("patch_id") or f"{layer}-patch"
        tile_id = payload.get("tile_id") or patch_id
        valid_time = payload.get("valid_time") or datetime.now(timezone.utc).isoformat()
        metadata = payload.get("metadata") or {}
        sql = f"""
            INSERT INTO {self.schema}.render_tiles
                (stable_id, layer, tile_id, patch_id, valid_time, source, status, feature_count, properties, geom, bbox, updated_at)
            VALUES
                (%s, %s, %s, %s, %s::timestamptz, %s, 'ready', %s, %s::jsonb,
                 ST_MakeEnvelope(%s, %s, %s, %s, 4326), ST_MakeEnvelope(%s, %s, %s, %s, 4326), now())
            ON CONFLICT (stable_id) DO UPDATE SET
                patch_id = EXCLUDED.patch_id, valid_time = EXCLUDED.valid_time, source = EXCLUDED.source,
                status = EXCLUDED.status, feature_count = EXCLUDED.feature_count, properties = EXCLUDED.properties,
                geom = EXCLUDED.geom, bbox = EXCLUDED.bbox, updated_at = now()
        """
        stable_id = f"{layer}:{tile_id}:{valid_time[:19]}"
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        stable_id, layer, tile_id, patch_id, valid_time, payload.get("source", "field_engine"), feature_count,
                        json.dumps({"metadata": metadata, "bbox": payload.get("bbox")}),
                        bbox.west, bbox.south, bbox.east, bbox.north,
                        bbox.west, bbox.south, bbox.east, bbox.north,
                    ),
                )

    def _cloud_particle_budget(self, feature: dict[str, Any]) -> int:
        family = feature.get("family", "cumulus")
        size = feature.get("size", "medium")
        base = {"micro": 8, "small": 18, "medium": 34, "large": 56, "massive": 88}.get(size, 34)
        if family in {"stratus", "marine-stratus"}:
            base = int(base * 1.35)
        if family == "cirrus":
            base = int(base * 0.75)
        if family == "cumulonimbus":
            base = int(base * 1.2)
        return max(6, min(128, base))

    def _cloud_row(self, row) -> dict[str, Any]:
        props = row[13] or {}
        bbox_geojson = json.loads(row[14]) if isinstance(row[14], str) else row[14]
        bbox = self._geojson_bbox(bbox_geojson)
        feature = dict(props)
        feature.update(
            {
                "id": row[0],
                "family": row[1],
                "render_style": row[2],
                "size": row[3],
                "density": round(float(row[4] or 0.0), 3),
                "opacity": round(float(row[5] or 0.0), 3),
                "altitude_m": round(float(row[6] or 0.0), 1),
                "thickness_m": round(float(row[7] or 0.0), 1),
                "wind_u": round(float(row[8] or 0.0), 3),
                "wind_v": round(float(row[9] or 0.0), 3),
                "rain_rate": round(float(row[10] or 0.0), 3),
                "particle_seed": row[11],
                "particle_budget": row[12],
                "centroid": {"lon": round(float(row[15] or 0.0), 6), "lat": round(float(row[16] or 0.0), 6)},
                "bbox": bbox,
                "title": props.get("title") or f"{row[1]} {row[3]} · {row[2]}",
            }
        )
        return feature

    def _ocean_row(self, row) -> dict[str, Any]:
        props = row[10] or {}
        bbox_geojson = json.loads(row[11]) if isinstance(row[11], str) else row[11]
        bbox = self._geojson_bbox(bbox_geojson)
        feature = dict(props)
        feature.update(
            {
                "id": row[0],
                "feature_type": row[1],
                "render_style": row[2],
                "depth_min_m": float(row[3] or 0.0),
                "depth_max_m": float(row[4] or 0.0),
                "speed": round(float(row[5] or 0.0), 3),
                "direction": round(float(row[6] or 0.0), 3),
                "score": round(float(row[7] or 0.0), 3),
                "u": float(props.get("u") or props.get("current_u") or 0.0),
                "v": float(props.get("v") or props.get("current_v") or 0.0),
                "particle_seed": row[8],
                "particle_budget": row[9],
                "lon": round(float(row[12] or 0.0), 6),
                "lat": round(float(row[13] or 0.0), 6),
                "bbox": bbox,
            }
        )
        return feature

    def _geojson_bbox(self, geom: dict[str, Any] | None) -> dict[str, float]:
        if not geom or "coordinates" not in geom:
            return {"west": 0.0, "south": 0.0, "east": 0.0, "north": 0.0}
        coords = geom["coordinates"]
        # Envelope polygons come back as Polygon coordinates: [[[lon,lat], ...]].
        points = coords[0] if geom.get("type") == "Polygon" else []
        lons = [float(p[0]) for p in points]
        lats = [float(p[1]) for p in points]
        return {"west": min(lons), "south": min(lats), "east": max(lons), "north": max(lats)} if lons and lats else {"west": 0.0, "south": 0.0, "east": 0.0, "north": 0.0}
