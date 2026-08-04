RTOFS_ALIASES = {
    "sst_c": [
        "sst", "sea_surface_temperature", "surface_temperature", "water_temp",
        "water_temp_c", "temperature", "sea_water_temperature",
        "Temperature_depth_below_surface", "temp", "tmpsfc",
    ],
    "water_temp_c": [
        "water_temp", "water_temp_c", "temperature", "sea_water_temperature",
        "Temperature_depth_below_surface", "temp", "sst",
    ],
    "current_u": [
        "u", "water_u", "u_velocity", "uvel", "water_u_velocity",
        "eastward_sea_water_velocity", "u-component_of_current",
        "u_component_of_current", "u_surface", "surf_u",
    ],
    "current_v": [
        "v", "water_v", "v_velocity", "vvel", "water_v_velocity",
        "northward_sea_water_velocity", "v-component_of_current",
        "v_component_of_current", "v_surface", "surf_v",
    ],
    "salinity": [
        "salinity", "sea_water_salinity", "Salinity_depth_below_surface",
        "sss", "surface_salinity", "saln", "salt",
    ],
    "depth_m": ["depth", "depth_m", "Depth_below_surface", "depth_below_surface", "lev", "z"],
}


def aliases_used() -> dict[str, list[str]]:
    return RTOFS_ALIASES
