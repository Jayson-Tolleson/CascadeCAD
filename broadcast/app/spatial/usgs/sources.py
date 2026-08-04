SOURCE_FAMILIES = ['3dhp', 'nhdplus_hr', 'nhd', 'arcgis_rest', 'geojson', 'shapefile_zip', 'mock']
STANDING_WATER_KINDS = {'lake', 'reservoir', 'pond', 'unknown_waterbody'}


def source_label(source_family: str) -> str:
    if source_family == '3dhp':
        return 'usgs_3dhp'
    if source_family == 'nhdplus_hr':
        return 'usgs_nhdplus_hr'
    if source_family == 'nhd':
        return 'usgs_nhd_legacy'
    if source_family == 'mock':
        return 'mock_spatial'
    return f'usgs_{source_family}'
