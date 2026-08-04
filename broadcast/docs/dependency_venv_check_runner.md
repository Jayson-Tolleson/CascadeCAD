# Python dependency and check-runner note

The app imports both `pydantic` and `pydantic_settings` directly. They are pinned in both:

- `pyproject.toml`
- `requirements.txt`

The installer now installs `requirements.txt`, installs the project editable, then verifies imports with:

```bash
python scripts/check_python_deps.py
```

The check scripts also re-exec into `.venv/bin/python` when they are launched with bare `python3`, so this works on the server:

```bash
python3 scripts/check_gfs_marine_land_mask.py
python3 scripts/check_ocean_tiled_landmask_shark_intel.py
```

For absolute clarity, this also works:

```bash
.venv/bin/python scripts/check_gfs_marine_land_mask.py
.venv/bin/python scripts/check_ocean_tiled_landmask_shark_intel.py
```
