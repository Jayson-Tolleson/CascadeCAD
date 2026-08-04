from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LFTR Next"
    host: str = "0.0.0.0"
    port: int = 8787
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    google_maps_api_key: str = ""

    # Deployment / Google Cloud / AI placeholders.
    # These are intentionally optional: the installer can write them during GCP/Vertex setup
    # without making app startup depend on Vertex integration being implemented yet.
    google_project_id: str = ""
    google_cloud_project: str = ""
    google_cloud_region: str = "global"
    vertex_location: str = "global"
    vertex_model: str = "gemini-2.5-flash"
    vertex_enabled: bool = False
    ai_provider: str = "none"
    ai_auth_mode: str = "unset"
    gcp_key: str = ""

    postgis_dsn: str | None = None
    postgis_enabled: bool = True
    postgis_schema: str = "lftr"
    spatial_mode: str = "postgis"
    spatial_tile_deg: float = 1.0

    # PostGIS pre-render cache: stores interpreted render features, not raw grids or final particles.
    render_cache_enabled: bool = True
    render_cache_prefer_postgis: bool = True
    render_cache_write_through: bool = True
    # PostGIS only caches live/last-good provider feature recipes by default.
    render_cache_allow_degraded: bool = False
    render_cache_max_features: int = 512
    render_cache_ttl_seconds: int = 1800
    geometry_simplify_global: float = 0.2
    geometry_simplify_regional: float = 0.05
    geometry_simplify_local: float = 0.005
    stream_tick_hz: float = 1.0
    target_stream_fps: str = "5-10"
    cache_root: str = "."

    # LFTR Field Engine Pass 1: dense x/y/z scalar fields shared by atmosphere and ocean.
    field_engine_grid_size: int = 64
    field_engine_max_tiles: int = 64
    field_engine_tile_workers: int = 16
    field_engine_tile_grid_size: int = 18
    field_engine_depth_levels_m: str = "0,10,25,50,100"
    cloud_feature_threshold: float = 0.22
    cloud_feature_max_features: int = 64
    ocean_feature_max_current_vectors: int = 72
    ocean_feature_max_bait_clusters: int = 48
    ocean_bait_threshold: float = 0.58
    marine_land_mask_enabled: bool = True
    marine_land_mask_sample_grid: int = 5
    marine_land_mask_coast_buffer_deg: float = 0.12
    marine_land_mask_allow_harbors_bays: bool = True
    provider_mode: str = "live"
    gfs_enabled: bool = True
    gfs_ncss_base_url: str = "https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best"
    gfs_ncss_fallback_url: str = "https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/TwoD"
    gfs_timeout_seconds: float = 8.0
    gfs_ttl_seconds: int = 900
    gfs_max_grid_points: int = 4096
    gfs_cache_dir: str = ".cache/gfs"
    rtofs_enabled: bool = True
    rtofs_nomads_base: str = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod"
    rtofs_timeout_seconds: float = 8.0
    rtofs_ttl_seconds: int = 900
    rtofs_cache_dir: str = ".cache/rtofs"
    rtofs_depth_levels: str = "surface"
    rtofs_max_grid_points: int = 256
    rtofs_provider_mode: str = "live"
    chl_enabled: bool = False
    chl_provider: str = "disabled"
    chl_erddap_base: str = "https://coastwatch.pfeg.noaa.gov/erddap"
    chl_dataset_id: str = ""
    chl_ttl_seconds: int = 21600
    chl_cache_dir: str = "data/cache/chlorophyll"
    usgs_enabled: bool = False
    usgs_source_family: str = "mock"
    usgs_cache_dir: str = "data/cache/usgs"
    usgs_timeout_seconds: float = 30.0
    usgs_max_features: int = 5000
    usgs_min_area_km2_global: float = 5.0
    usgs_min_area_km2_regional: float = 0.25
    usgs_min_area_km2_local: float = 0.01
    usgs_simplify_global: float = 0.01
    usgs_simplify_regional: float = 0.0025
    usgs_simplify_local: float = 0.0005
    usgs_arcgis_url: str = ""
    usgs_arcgis_layer: str = ""
    usgs_geojson_path: str = ""
    usgs_shapefile_zip_path: str = ""
    usgs_default_bbox: str = "-125,32,-117,38"
    lightning_enabled: bool = False
    lightning_provider: str = "disabled"
    lightning_ttl_seconds: int = 120
    lightning_max_flashes: int = 50
    lightning_cache_dir: str = "data/cache/lightning"
    broadcast_default_room: str = "default"
    broadcast_max_message_chars: int = 2000
    broadcast_uploads_enabled: bool = False
    broadcast_upload_dir: str = "data/uploads/broadcast"

    # Cross-browser broadcaster speech-to-text. Chrome may use native Web Speech;
    # Firefox falls back to /ws/stt with MediaRecorder audio chunks and Google STT when enabled.
    stt_enabled: bool = True
    stt_provider: str = "google"
    stt_language_code: str = "en-US"
    stt_model: str = "latest_short"
    stt_sample_rate_hz: int = 48000
    stt_chunk_seconds: float = 3.5

    model_config = SettingsConfigDict(env_file=".env", env_prefix="LFTR_", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
