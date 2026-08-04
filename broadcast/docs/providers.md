# LFTR Provider Catalog

Runtime configuration is authoritative. URLs below are source templates/examples for future parser work; the app reads configured values from environment settings.

## GFS NCSS Atmosphere

- Provider ID: `gfs_ncss_atmosphere`
- Role: moving atmosphere field truth
- Source type: NCSS/THREDDS-style subset service
- Purpose: clouds, rain, wind, humidity, temperature, pressure
- Status: provider adapter / live probe / parser TODO
- Default/source template: `https://thredds.ucar.edu/thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best`
- Runtime base URL: `LFTR_GFS_NCSS_BASE_URL`

NCSS request parameters: repeated `var=...`, `north`, `south`, `east`, `west`, `time=present`, `accept=netcdf4`, `addLatLon=true`.

Variables: `Temperature_height_above_ground`, `Relative_humidity_height_above_ground`, `Dewpoint_temperature_height_above_ground`, `Pressure_reduced_to_MSL_msl`, `Total_cloud_cover_entire_atmosphere`, `Low_cloud_cover_low_cloud`, `Medium_cloud_cover_middle_cloud`, `High_cloud_cover_high_cloud`, `Precipitation_rate_surface`, `u-component_of_wind_height_above_ground`, `v-component_of_wind_height_above_ground`.

Normalized channels: `cloud_density`, `rain_rate`, `wind_u`, `wind_v`, `humidity`, `temperature`, `pressure`.

Mapping intent: total/low/mid/high cloud cover → `cloud_density`; precipitation rate → `rain_rate`; u/v wind → `wind_u`/`wind_v`; relative humidity → `humidity`; temperature → `temperature`; pressure MSL → `pressure`.

## RTOFS/NOMADS Ocean

- Provider ID: `rtofs_ncep_ocean`
- Role: moving ocean field truth
- Source type: NOAA/NCEP NOMADS RTOFS NetCDF products
- Purpose: SST, current vectors, salinity, depth, bait score support
- Status: provider adapter / live probe / parser TODO
- Runtime base: `LFTR_RTOFS_NOMADS_BASE`
- Default/source template: `https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.YYYYMMDD/`

Product files to probe/parse: `rtofs_glo_2ds_n000_diag.nc`, `rtofs_glo_2ds_n000_prog.nc`; future 3D files may be added when configured.

Aliases: SST/water temperature (`sst`, `temperature`, `water_temp`); current u (`u`, `water_u`, `u_velocity`, `current_u`); current v (`v`, `water_v`, `v_velocity`, `current_v`); salinity (`salinity`, `salt`); depth (`depth`, `depth_m`).

Normalized channels: `sst_c`, `current_u`, `current_v`, `current_speed`, `current_direction`, `salinity`, `depth_m`, `bait_score`.

Mapping intent: SST/water temperature → `sst_c`; u/v current → `current_u`/`current_v`; speed/direction are derived; salinity aliases → `salinity`; depth coordinate/metadata → `depth_m`; bait score derives from SST/current/depth/chlorophyll when available.

Future 3D sampler interface: `sample(lon, lat, depth_m, time)`. Surface is depth `0`; future depth levels are configured by `LFTR_RTOFS_DEPTH_LEVELS`.

## Chlorophyll / Ocean Color Future Booster

- Provider ID: `chlorophyll_ocean_color`
- Role: ocean biology booster for bait score
- Source type: satellite ocean color / ERDDAP / NASA OceanColor
- Status: disabled future adapter
- NOAA CoastWatch ERDDAP: `https://coastwatch.pfeg.noaa.gov/erddap/`
- NASA OceanColor / OB.DAAC: `https://oceancolor.gsfc.nasa.gov/`

Possible aliases: `chlor_a`, `chlorophyll`, `chlorophyll_a`, `chlor_a_concentration`, `mass_concentration_of_chlorophyll_a_in_sea_water`.

Normalized channel: `chlorophyll_mg_m3`.

Chlorophyll is a bait-score booster, not a blocker. If chlorophyll is missing, bait score still computes from SST/current/depth. Dataset selection is TODO based on near-real-time availability, spatial resolution, cadence, coastal coverage, variable consistency, public/no-token access if possible, and ERDDAP griddap compatibility.

## USGS Hydrography Stable Spatial Truth

- Provider ID: `usgs_hydrography`
- Role: stable spatial truth
- Source families: `3dhp`, `nhdplus_hr`, `nhd`, `arcgis_rest`, `geojson`, `shapefile_zip`, `mock`
- Normalized entity: `waterbody`
- Status: optional spatial ingest
- Output: PostGIS `waterbodies` table and `/gfs/api/viewport-spatial` waterbodies/lakes

3DHP/current hydrography should be preferred when configured. NHDPlus HR and NHD are supported as legacy/reference families. Runtime configuration is authoritative; mock and local GeoJSON modes keep checks offline.
