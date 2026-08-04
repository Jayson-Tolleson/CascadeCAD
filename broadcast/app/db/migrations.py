from pathlib import Path
from app.core.config import get_settings
from app.db.connect import postgis_connection


def schema_sql() -> str:
    settings = get_settings()
    sql = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    return sql.replace("{{SCHEMA}}", settings.postgis_schema)


def run_migrations() -> dict:
    with postgis_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql())
    return {"ok": True, "schema": get_settings().postgis_schema}
