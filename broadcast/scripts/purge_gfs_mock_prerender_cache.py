#!/usr/bin/env python3
"""Purge synthetic/legacy render recipes from the optional PostGIS prerender cache.

Default is dry-run. Use --apply after installing the truth-guard build if your database
already contains old synthetic cloud/ocean recipes from earlier builds.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.connect import postgis_connection, safe_postgis_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually delete synthetic/legacy cache rows")
    args = parser.parse_args()

    settings = get_settings()
    status = safe_postgis_status()
    if not status.get("enabled") or not status.get("configured"):
        print(json.dumps({"ok": True, "skipped": True, "reason": "PostGIS disabled or not configured", "postgis": status}))
        return 0

    schema = settings.postgis_schema
    queries = {
        "cloud_render_features": f"""
            FROM {schema}.cloud_render_features
            WHERE COALESCE(properties->>'_lftr_source_kind', '') <> 'live_provider'
        """,
        "ocean_render_features": f"""
            FROM {schema}.ocean_render_features
            WHERE COALESCE(properties->>'_lftr_source_kind', '') <> 'live_provider'
        """,
    }
    result: dict[str, object] = {"ok": True, "dry_run": not args.apply, "schema": schema, "tables": {}}
    with postgis_connection() as conn:
        with conn.cursor() as cur:
            for table, where_sql in queries.items():
                cur.execute(f"SELECT count(*) {where_sql}")
                count = int(cur.fetchone()[0])
                if args.apply and count:
                    cur.execute(f"DELETE {where_sql}")
                result["tables"][table] = {"mock_or_unmarked_rows": count, "deleted": count if args.apply else 0}
        if args.apply:
            conn.commit()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
