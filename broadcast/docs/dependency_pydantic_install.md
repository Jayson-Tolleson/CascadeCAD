# Pydantic install dependency patch

This patch makes the Python dependency set explicit for both direct imports used by the app:

- `pydantic>=2.7,<3.0`
- `pydantic-settings>=2.3,<3.0`

The dependencies are listed in `pyproject.toml` and mirrored in `requirements.txt` for simple server repair commands. The main installer also explicitly installs both packages after `pip install -e .`, so existing virtualenvs are repaired when the installer is rerun.

Quick server repair:

```bash
cd ~/broadcast
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install "pydantic>=2.7,<3.0" "pydantic-settings>=2.3,<3.0"
.venv/bin/python scripts/check_gfs_marine_land_mask.py
.venv/bin/python scripts/check_ocean_tiled_landmask_shark_intel.py
```
