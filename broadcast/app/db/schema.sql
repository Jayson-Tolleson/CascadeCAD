CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS {{SCHEMA}};

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.spatial_metadata (
    key text PRIMARY KEY,
    value jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.spatial_reports (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    title text NOT NULL,
    source text NOT NULL DEFAULT 'csv',
    source_id text,
    kind text NOT NULL DEFAULT 'report',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Point, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS spatial_reports_geom_gix ON {{SCHEMA}}.spatial_reports USING gist (geom);
CREATE INDEX IF NOT EXISTS spatial_reports_label_gix ON {{SCHEMA}}.spatial_reports USING gist (label_point);
CREATE INDEX IF NOT EXISTS spatial_reports_kind_idx ON {{SCHEMA}}.spatial_reports (kind);
CREATE INDEX IF NOT EXISTS spatial_reports_source_idx ON {{SCHEMA}}.spatial_reports (source, source_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.waterbodies (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    name text NOT NULL,
    source text NOT NULL,
    source_id text,
    kind text NOT NULL DEFAULT 'waterbody',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    area_km2 double precision NOT NULL DEFAULT 0,
    ingest_batch_id text,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS waterbodies_geom_gix ON {{SCHEMA}}.waterbodies USING gist (geom);
CREATE INDEX IF NOT EXISTS waterbodies_label_gix ON {{SCHEMA}}.waterbodies USING gist (label_point);
CREATE INDEX IF NOT EXISTS waterbodies_kind_idx ON {{SCHEMA}}.waterbodies (kind);
CREATE INDEX IF NOT EXISTS waterbodies_source_idx ON {{SCHEMA}}.waterbodies (source, source_id);
CREATE INDEX IF NOT EXISTS waterbodies_stable_id_idx ON {{SCHEMA}}.waterbodies (stable_id);
CREATE INDEX IF NOT EXISTS waterbodies_ingest_batch_idx ON {{SCHEMA}}.waterbodies (ingest_batch_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.harbors (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    name text NOT NULL,
    source text NOT NULL,
    source_id text,
    kind text NOT NULL DEFAULT 'harbor',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Point, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS harbors_geom_gix ON {{SCHEMA}}.harbors USING gist (geom);
CREATE INDEX IF NOT EXISTS harbors_label_gix ON {{SCHEMA}}.harbors USING gist (label_point);
CREATE INDEX IF NOT EXISTS harbors_kind_idx ON {{SCHEMA}}.harbors (kind);
CREATE INDEX IF NOT EXISTS harbors_source_idx ON {{SCHEMA}}.harbors (source, source_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.coast_masks (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    name text NOT NULL,
    source text NOT NULL,
    source_id text,
    kind text NOT NULL DEFAULT 'coast_mask',
    tier text NOT NULL DEFAULT 'regional',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS coast_masks_geom_gix ON {{SCHEMA}}.coast_masks USING gist (geom);
CREATE INDEX IF NOT EXISTS coast_masks_label_gix ON {{SCHEMA}}.coast_masks USING gist (label_point);
CREATE INDEX IF NOT EXISTS coast_masks_kind_idx ON {{SCHEMA}}.coast_masks (kind);
CREATE INDEX IF NOT EXISTS coast_masks_source_idx ON {{SCHEMA}}.coast_masks (source, source_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.spatial_tiles (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    name text NOT NULL,
    source text NOT NULL DEFAULT 'lftr',
    source_id text,
    kind text NOT NULL DEFAULT 'tile',
    tier text NOT NULL DEFAULT 'regional',
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Polygon, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS spatial_tiles_geom_gix ON {{SCHEMA}}.spatial_tiles USING gist (geom);
CREATE INDEX IF NOT EXISTS spatial_tiles_label_gix ON {{SCHEMA}}.spatial_tiles USING gist (label_point);
CREATE INDEX IF NOT EXISTS spatial_tiles_kind_idx ON {{SCHEMA}}.spatial_tiles (kind);
CREATE INDEX IF NOT EXISTS spatial_tiles_source_idx ON {{SCHEMA}}.spatial_tiles (source, source_id);

ALTER TABLE IF EXISTS {{SCHEMA}}.waterbodies ADD COLUMN IF NOT EXISTS area_km2 double precision NOT NULL DEFAULT 0;
ALTER TABLE IF EXISTS {{SCHEMA}}.waterbodies ADD COLUMN IF NOT EXISTS ingest_batch_id text;
CREATE INDEX IF NOT EXISTS waterbodies_ingest_batch_idx ON {{SCHEMA}}.waterbodies (ingest_batch_id);

-- LFTR PostGIS Pre-Render Feature Store
-- Stores interpreted render features, not raw provider grids and not final frontend particles.
-- Frontend receives feature recipes/geometry and creates stable particles from seed/budget.

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.render_tiles (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    layer text NOT NULL,
    tile_id text NOT NULL,
    patch_id text,
    valid_time timestamptz NOT NULL,
    source text NOT NULL DEFAULT 'field_engine',
    status text NOT NULL DEFAULT 'ready',
    feature_count integer NOT NULL DEFAULT 0,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Polygon, 4326) NOT NULL,
    bbox geometry(Polygon, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS render_tiles_geom_gix ON {{SCHEMA}}.render_tiles USING gist (geom);
CREATE INDEX IF NOT EXISTS render_tiles_layer_time_idx ON {{SCHEMA}}.render_tiles (layer, valid_time DESC);
CREATE INDEX IF NOT EXISTS render_tiles_tile_idx ON {{SCHEMA}}.render_tiles (tile_id, layer);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.cloud_render_features (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    patch_id text,
    tile_id text NOT NULL,
    valid_time timestamptz NOT NULL,
    family text NOT NULL,
    render_style text NOT NULL,
    size text NOT NULL DEFAULT 'medium',
    density double precision NOT NULL DEFAULT 0,
    opacity double precision NOT NULL DEFAULT 0.35,
    altitude_m double precision NOT NULL DEFAULT 0,
    thickness_m double precision NOT NULL DEFAULT 0,
    wind_u double precision NOT NULL DEFAULT 0,
    wind_v double precision NOT NULL DEFAULT 0,
    rain_factor double precision NOT NULL DEFAULT 0,
    particle_seed text NOT NULL,
    particle_budget integer NOT NULL DEFAULT 32,
    area_cells integer NOT NULL DEFAULT 0,
    area_km2 double precision NOT NULL DEFAULT 0,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Geometry, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cloud_render_features_geom_gix ON {{SCHEMA}}.cloud_render_features USING gist (geom);
CREATE INDEX IF NOT EXISTS cloud_render_features_family_idx ON {{SCHEMA}}.cloud_render_features (family, render_style);
CREATE INDEX IF NOT EXISTS cloud_render_features_time_idx ON {{SCHEMA}}.cloud_render_features (valid_time DESC);
CREATE INDEX IF NOT EXISTS cloud_render_features_tile_idx ON {{SCHEMA}}.cloud_render_features (tile_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.ocean_render_features (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    patch_id text,
    tile_id text NOT NULL,
    valid_time timestamptz NOT NULL,
    feature_type text NOT NULL,
    render_style text NOT NULL,
    depth_min_m double precision NOT NULL DEFAULT 0,
    depth_max_m double precision NOT NULL DEFAULT 0,
    speed double precision NOT NULL DEFAULT 0,
    direction double precision NOT NULL DEFAULT 0,
    score double precision NOT NULL DEFAULT 0,
    particle_seed text NOT NULL,
    particle_budget integer NOT NULL DEFAULT 12,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Geometry, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ocean_render_features_geom_gix ON {{SCHEMA}}.ocean_render_features USING gist (geom);
CREATE INDEX IF NOT EXISTS ocean_render_features_type_idx ON {{SCHEMA}}.ocean_render_features (feature_type, render_style);
CREATE INDEX IF NOT EXISTS ocean_render_features_time_idx ON {{SCHEMA}}.ocean_render_features (valid_time DESC);
CREATE INDEX IF NOT EXISTS ocean_render_features_tile_idx ON {{SCHEMA}}.ocean_render_features (tile_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.bait_render_features (
    id bigserial PRIMARY KEY,
    stable_id text NOT NULL UNIQUE,
    patch_id text,
    tile_id text NOT NULL,
    valid_time timestamptz NOT NULL,
    family text NOT NULL DEFAULT 'bait_cluster',
    score double precision NOT NULL DEFAULT 0,
    depth_min_m double precision NOT NULL DEFAULT 0,
    depth_max_m double precision NOT NULL DEFAULT 0,
    particle_seed text NOT NULL,
    particle_budget integer NOT NULL DEFAULT 24,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    geom geometry(Geometry, 4326) NOT NULL,
    label_point geometry(Point, 4326),
    bbox geometry(Polygon, 4326),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bait_render_features_geom_gix ON {{SCHEMA}}.bait_render_features USING gist (geom);
CREATE INDEX IF NOT EXISTS bait_render_features_time_idx ON {{SCHEMA}}.bait_render_features (valid_time DESC);
CREATE INDEX IF NOT EXISTS bait_render_features_tile_idx ON {{SCHEMA}}.bait_render_features (tile_id);
