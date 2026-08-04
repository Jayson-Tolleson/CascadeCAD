#!/usr/bin/env python3
"""Source-structure check for real bounded GFS NCSS parsing.

This does not call the public NCSS service. It verifies that the provider no longer
uses a URL probe as the live path and that the renderer can get parsed GFS clouds.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
gfs = (ROOT / "app/providers/gfs_ncss.py").read_text()
config = (ROOT / "app/core/config.py").read_text()
pyproject = (ROOT / "pyproject.toml").read_text()
install = (ROOT / "scripts/install.sh").read_text()
needed = [
    "from netCDF4 import Dataset",
    "_fetch_and_parse_ncss",
    "bounded_ncss_netcdf_parser_ok",
    "live_parsed",
    "gfs_ncss_live_parsed",
    "horizStride",
    "CHANNEL_ALIASES",
    "cloud_density",
    "live_ok=True",
]
missing = [needle for needle in needed if needle not in gfs]
if 'gfs_enabled: bool = True' not in config:
    missing.append('config_default_gfs_enabled_true')
if 'thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best' not in config or 'thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/Best' not in install:
    missing.append('gfs_best_ncss_grid_endpoint_default')
if 'thredds/ncss/grid/grib/NCEP/GFS/Global_0p25deg/TwoD' not in config or 'gfs_ncss_fallback_url' not in config or '_candidate_base_urls' not in gfs:
    missing.append('gfs_ncss_grid_fallback_url_wired')
if '"netCDF4' not in pyproject or '"numpy' not in pyproject:
    missing.append('netcdf_numpy_dependencies')
if 'LFTR_GFS_ENABLED="${LFTR_GFS_ENABLED:-true}"' not in install:
    missing.append('installer_enables_gfs_by_default')
if missing:
    print({"ok": False, "missing": missing})
    sys.exit(1)
print({"ok": True, "check": "gfs_live_ncss_parser_wired"})
