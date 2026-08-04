# Installer apt pydantic fallback + ProviderStatus compatibility

This patch adds Debian/Ubuntu system packages to the installer:

```bash
sudo apt install -y python3-pydantic python3-pydantic-settings
```

The app still installs dependencies into `.venv` using `requirements.txt` and
`pip install -e .`. The apt packages are a server-diagnostic fallback for cases
where operators run `python3 scripts/check_*.py` before the venv is active.

`ProviderStatus` now exposes a computed `ok` property in addition to the existing
`live_ok` field. Direct diagnostics like this no longer crash:

```python
frame, status = get_rtofs_provider().fetch_ocean(bbox)
print(status.ok)
```

`check_rtofs_provider.py` now defaults to the installer port from
`/etc/broadcast/install.env`, then `8787`, with an old `8000` fallback only when
`BASE_URL` is not set.
