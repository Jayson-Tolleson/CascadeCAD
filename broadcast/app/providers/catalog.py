from app.core.config import get_settings
from app.providers.gfs_ncss import GFS_VARIABLES, build_ncss_url
from app.providers.rtofs_aliases import aliases_used
from app.providers.rtofs_ncep import build_rtofs_url, parse_depth_levels
from app.fields.tiles import default_field_bbox
from app.spatial.usgs.catalog import usgs_catalog_entry

ATMOSPHERE_CHANNELS = ["cloud_density", "rain_rate", "wind_u", "wind_v", "humidity", "temperature", "pressure"]
OCEAN_CHANNELS = ["sst_c", "current_u", "current_v", "current_speed", "current_direction", "salinity", "depth_m", "bait_score"]
CHL_ALIASES = ["chlor_a", "chlorophyll", "chlorophyll_a", "chlor_a_concentration", "mass_concentration_of_chlorophyll_a_in_sea_water"]


def provider_catalog() -> dict:
    settings = get_settings()
    bbox = default_field_bbox()
    depth_levels = parse_depth_levels(settings.rtofs_depth_levels)
    gfs_url = build_ncss_url(settings.gfs_ncss_base_url, bbox, settings.gfs_max_grid_points)
    rtofs_url = build_rtofs_url(settings.rtofs_nomads_base, bbox, depth_levels, settings.rtofs_max_grid_points)
    return {
        "ok": True,
        "providers": {
            "gfs_ncss_atmosphere": {
                "provider_id": "gfs_ncss_atmosphere",
                "provider_name": "GFS NCSS Atmosphere",
                "role": "moving atmosphere field truth",
                "source_type": "NCSS/THREDDS-style subset service",
                "configured_base_url": settings.gfs_ncss_base_url,
                "fallback_base_url": settings.gfs_ncss_fallback_url,
                "default_source_template": "https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best",
                "request_pattern": "var repeated, north/south/east/west bbox, time=present, accept=netcdf4, addLatLon=true",
                "request_url_example": gfs_url,
                "expected_variables": GFS_VARIABLES,
                "normalized_channels": ATMOSPHERE_CHANNELS,
                "units": {"cloud_density": "0-1 derived from cloud cover", "rain_rate": "provider precipitation rate normalized for renderer", "wind_u": "m/s eastward", "wind_v": "m/s northward", "humidity": "percent or 0-1 normalized", "temperature": "C or K mapped to C TODO", "pressure": "Pa or hPa TODO"},
                "parser_status": "bounded_ncss_netcdf_parser_enabled",
                "live_status": "live_parsed_or_no_data",
                "cache_status": "last_good_cache supported",
                "degraded": False,
                "todo": ["Improve variable alias coverage", "Keep request paths bounded by viewport"],
            },
            "rtofs_ncep_ocean": {
                "provider_id": "rtofs_ncep_ocean",
                "provider_name": "RTOFS/NOMADS Ocean",
                "role": "moving ocean field truth",
                "source_type": "NOAA/NCEP NOMADS RTOFS NetCDF products",
                "nomads_base": settings.rtofs_nomads_base,
                "default_source_template": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.YYYYMMDD/",
                "product_files": ["rtofs_glo_2ds_n000_diag.nc", "rtofs_glo_2ds_n000_prog.nc"],
                "request_pattern": "bounded bbox/depth subset probe now; NetCDF parser TODO",
                "request_url_example": rtofs_url,
                "aliases": aliases_used(),
                "normalized_channels": OCEAN_CHANNELS,
                "depth_levels": depth_levels,
                "units": {"sst_c": "degrees C", "current_u": "m/s eastward", "current_v": "m/s northward", "current_speed": "m/s", "current_direction": "degrees from east counterclockwise", "salinity": "PSU", "depth_m": "m", "bait_score": "0-1 derived scalar"},
                "parser_status": "bounded_NetCDF_parser_TODO_no_synthetic_output",
                "live_status": "no_data_until_bounded_parser",
                "cache_status": "last_good_cache supported",
                "degraded": False,
                "todo": ["Implement bounded NOMADS/NetCDF subset parsing", "Support sample(lon, lat, depth_m, time)", "Do not download giant whole-world files in request paths"],
            },
            "usgs_hydrography": usgs_catalog_entry(),
            "chlorophyll_ocean_color": {
                "provider_id": "chlorophyll_ocean_color",
                "provider_name": "Chlorophyll / Ocean Color Future Booster",
                "role": "ocean biology booster for bait score",
                "source_type": "satellite ocean color / ERDDAP / NASA OceanColor",
                "provider": settings.chl_provider,
                "enabled": settings.chl_enabled,
                "erddap_base": settings.chl_erddap_base,
                "dataset_id": settings.chl_dataset_id,
                "source_families": ["NOAA CoastWatch ERDDAP griddap", "NASA OceanColor / OB.DAAC MODIS VIIRS PACE"],
                "possible_variables": CHL_ALIASES,
                "normalized_channels": ["chlorophyll_mg_m3"],
                "units": {"chlorophyll_mg_m3": "mg/m^3"},
                "parser_status": "disabled_future_adapter",
                "live_status": "disabled by default; must not block ocean rendering",
                "cache_status": f"future cache ttl {settings.chl_ttl_seconds}s in {settings.chl_cache_dir}",
                "degraded": True,
                "todo": ["Select dataset by near-real-time availability, resolution, cadence, coastal coverage, variable consistency, no-token/public access, and ERDDAP griddap compatibility", "Use chlorophyll as bait_score booster, never blocker"],
            },
        },
    }
