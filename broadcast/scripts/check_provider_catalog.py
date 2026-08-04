#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.providers.catalog import provider_catalog

catalog = provider_catalog()
text = json.dumps(catalog)
for forbidden in ['POSTGIS_DSN', 'postgresql://', 'password=']:
    if forbidden in text:
        raise SystemExit(f'provider catalog leaked secret-like value: {forbidden}')
providers = catalog['providers']
gfs = providers['gfs_ncss_atmosphere']
rtofs = providers['rtofs_ncep_ocean']
chl = providers['chlorophyll_ocean_color']
usgs = providers['usgs_hydrography']
assert gfs['configured_base_url'] and gfs['request_url_example']
assert 'Temperature_height_above_ground' in gfs['expected_variables']
assert 'cloud_density' in gfs['normalized_channels']
assert rtofs['nomads_base'] and rtofs['product_files']
assert 'sst_c' in rtofs['normalized_channels']
assert 'current_u' in rtofs['aliases']
assert chl['provider_id'] == 'chlorophyll_ocean_color'
assert chl['parser_status'] == 'disabled_future_adapter'
assert usgs['normalized_entity'] == 'waterbody'
assert 'mock' in usgs['source_families']
print(json.dumps({'ok': True, 'providers': list(providers)}))
