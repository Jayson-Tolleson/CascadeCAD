def label_anchor_sql(geom_column: str = "geom") -> str:
    return f"COALESCE(label_point, ST_PointOnSurface({geom_column}))"
