import json
from app.core.config import get_settings
from app.db.connect import postgis_connection, safe_postgis_status
from app.schemas.scene import BBox
from app.spatial.csv_reports import load_reports
from app.spatial.geometry_simplify import simplify_tolerance
from pathlib import Path


def bbox_wkt(bbox: BBox) -> str:
    return f"POLYGON(({bbox.west} {bbox.south},{bbox.east} {bbox.south},{bbox.east} {bbox.north},{bbox.west} {bbox.north},{bbox.west} {bbox.south}))"


class PostGISSpatialRepository:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.schema = self.settings.postgis_schema

    def available(self) -> bool:
        status = safe_postgis_status()
        return self.settings.postgis_enabled and status["configured"] and status["driver_available"]

    def status(self) -> dict:
        status = safe_postgis_status()
        status.update({"spatial_mode": self.settings.spatial_mode, "tile_deg": self.settings.spatial_tile_deg})
        return status

    def query_reports(self, bbox: BBox) -> list[dict]:
        sql = f"""
            SELECT stable_id, title, kind, source, properties, ST_Y(geom) AS lat, ST_X(geom) AS lon
            FROM {self.schema}.spatial_reports
            WHERE geom && ST_GeomFromText(%s, 4326) AND ST_Intersects(geom, ST_GeomFromText(%s, 4326))
            ORDER BY updated_at DESC
            LIMIT 200
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (bbox_wkt(bbox), bbox_wkt(bbox)))
                return [self._report(row) for row in cursor.fetchall()]

    def query_harbors(self, bbox: BBox) -> list[dict]:
        return self._query_point_features("harbors", bbox)

    def query_waterbodies(self, bbox: BBox, tier: str) -> list[dict]:
        tolerance = simplify_tolerance(tier)
        sql = f"""
            SELECT stable_id, name, kind, source, properties, ST_Y(ST_PointOnSurface(geom)) AS lat, ST_X(ST_PointOnSurface(geom)) AS lon,
                   ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s)) AS geometry, area_km2, source_id, ingest_batch_id, ST_AsGeoJSON(ST_Envelope(geom)) AS bbox_geojson
            FROM {self.schema}.waterbodies
            WHERE geom && ST_GeomFromText(%s, 4326) AND ST_Intersects(geom, ST_GeomFromText(%s, 4326))
            LIMIT 100
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (tolerance, bbox_wkt(bbox), bbox_wkt(bbox)))
                return [self._feature(row, include_geometry=True) for row in cursor.fetchall()]

    def query_coast_mask(self, bbox: BBox, tier: str) -> dict | None:
        sql = f"""
            SELECT stable_id, tier, properties
            FROM {self.schema}.coast_masks
            WHERE tier = %s AND geom && ST_GeomFromText(%s, 4326)
            LIMIT 1
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (tier, bbox_wkt(bbox)))
                row = cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "tier": row[1], "properties": row[2] or {}, "status": "postgis"}

    def load_reports_csv(self) -> dict:
        root = Path(__file__).resolve().parents[2]
        fish_locations = root / "data" / "fishloclist.csv"
        reports_path = fish_locations if fish_locations.exists() else root / "data" / "reports.csv"
        reports = load_reports(reports_path)
        sql = f"""
            INSERT INTO {self.schema}.spatial_reports (stable_id, title, source, source_id, kind, properties, geom, label_point, bbox, generated_at, updated_at)
            VALUES (%s, %s, 'csv', %s, 'report', %s::jsonb, ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_Envelope(ST_SetSRID(ST_MakePoint(%s, %s), 4326)), now(), now())
            ON CONFLICT (stable_id) DO UPDATE SET title = EXCLUDED.title, properties = EXCLUDED.properties, geom = EXCLUDED.geom, label_point = EXCLUDED.label_point, updated_at = now()
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                for report in reports:
                    props = json.dumps(report.model_dump(mode="json"))
                    cursor.execute(sql, (report.id, report.title, report.id, props, report.longitude, report.latitude, report.longitude, report.latitude, report.longitude, report.latitude))
        return {"ok": True, "loaded": len(reports)}


    def upsert_waterbodies(self, waterbodies) -> dict:
        sql = f"""
            INSERT INTO {self.schema}.waterbodies (stable_id, name, source, source_id, kind, properties, area_km2, ingest_batch_id, geom, label_point, bbox, generated_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_MakeEnvelope(%s, %s, %s, %s, 4326), now(), now())
            ON CONFLICT (stable_id) DO UPDATE SET name = EXCLUDED.name, source = EXCLUDED.source, source_id = EXCLUDED.source_id, kind = EXCLUDED.kind, properties = EXCLUDED.properties, area_km2 = EXCLUDED.area_km2, ingest_batch_id = EXCLUDED.ingest_batch_id, geom = EXCLUDED.geom, label_point = EXCLUDED.label_point, bbox = EXCLUDED.bbox, updated_at = now()
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                for item in waterbodies:
                    cursor.execute(sql, (item.stable_id, item.name, item.source, item.source_id, item.kind, json.dumps(item.properties), item.area_km2, item.ingest_batch_id, json.dumps(item.geom), item.label_point['lon'], item.label_point['lat'], item.bbox[0], item.bbox[1], item.bbox[2], item.bbox[3]))
        return {"ok": True, "loaded": len(waterbodies)}

    def _query_point_features(self, table: str, bbox: BBox) -> list[dict]:
        sql = f"""
            SELECT stable_id, name, kind, source, properties, ST_Y(geom) AS lat, ST_X(geom) AS lon
            FROM {self.schema}.{table}
            WHERE geom && ST_GeomFromText(%s, 4326) AND ST_Intersects(geom, ST_GeomFromText(%s, 4326))
            LIMIT 100
        """
        with postgis_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (bbox_wkt(bbox), bbox_wkt(bbox)))
                return [self._feature(row) for row in cursor.fetchall()]

    def _report(self, row) -> dict:
        props = row[4] or {}
        csv_fields = props.get("csv_fields") if isinstance(props.get("csv_fields"), dict) else {}
        report_indices = props.get("report_indices") if isinstance(props.get("report_indices"), list) else []
        marine_mask = props.get("marine_mask") if isinstance(props.get("marine_mask"), dict) else {}
        return {
            "id": row[0],
            "kind": row[2],
            "title": row[1],
            "source": props.get("source") or row[3],
            "summary": props.get("summary", ""),
            "observed_at": props.get("observed_at", ""),
            "latitude": row[5],
            "longitude": row[6],
            "csv_fields": csv_fields,
            "report_indices": report_indices,
            "marine_mask": marine_mask,
        }

    def _feature(self, row, include_geometry: bool = False) -> dict:
        feature = {"id": row[0], "stable_id": row[0], "name": row[1], "label": row[1], "kind": row[2], "source": row[3], "properties": row[4] or {}, "metadata": row[4] or {}, "label_point": {"lat": row[5], "lon": row[6]}, "latitude": row[5], "longitude": row[6]}
        if include_geometry:
            feature["geometry"] = json.loads(row[7]) if isinstance(row[7], str) else row[7]
        if len(row) > 8:
            feature["area_km2"] = row[8]
            feature["source_id"] = row[9]
            feature["ingest_batch_id"] = row[10]
        return feature
