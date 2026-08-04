# USGS Hydrography Ingest (#7)

Pass #7 adds stable inland-water geometry only. USGS 3DHP/current hydrography should be preferred when configured; NHDPlus HR and NHD are legacy/reference source families. The app still runs without network and without PostGIS.

Supported source families: `3dhp`, `nhdplus_hr`, `nhd`, `arcgis_rest`, `geojson`, `shapefile_zip`, and `mock`.

Waterbodies normalize to stable LFTR objects with `stable_id`, source/source family, source ID, name, kind, area, geometry, label point, bbox, properties, and ingest batch ID. Standing polygonal waterbodies (lakes, reservoirs, ponds) are the viewport priority; rivers may be stored later but are not the main visual goal in this pass.

Live lake temperature, bait/boats, lightning, and broadcast/watch migration are later passes. Waterbody geometry persists independently of weather/ocean fields.
