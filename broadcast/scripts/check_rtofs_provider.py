#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(ROOT)
except Exception:
    pass


def _read_install_port() -> str | None:
    env_path = Path('/etc/broadcast/install.env')
    if not env_path.exists():
        return None
    for line in env_path.read_text(errors='ignore').splitlines():
        if line.startswith('APP_PORT='):
            value = line.split('=', 1)[1].strip().strip('"')
            if value:
                return value
    return None


def _candidate_base_urls() -> list[str]:
    explicit = os.environ.get('BASE_URL')
    if explicit:
        return [explicit.rstrip('/')]
    port = _read_install_port() or os.environ.get('LFTR_PORT') or '8787'
    urls = [f'http://127.0.0.1:{port}']
    # Historical fallback for older local commands; only used if no BASE_URL set.
    if port != '8000':
        urls.append('http://127.0.0.1:8000')
    return urls


def _fetch(url: str) -> dict:
    timeout = int(os.environ.get('RTOFS_CHECK_TIMEOUT', '20'))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def main() -> None:
    bbox = os.environ.get('BBOX', '-87.8,18.0,-73.0,32.5')
    errors: list[str] = []
    for base_url in _candidate_base_urls():
        url = f'{base_url.rstrip()}/gfs/api/providers/rtofs?{urllib.parse.urlencode({"bbox": bbox})}'
        try:
            data = _fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f'{url}: {exc}')
            continue
        if not data.get('ok'):
            raise SystemExit(f'RTOFS provider response was not ok from {url}: {data}')
        frame = data.get('frame', {})
        channels = frame.get('channels', {})
        missing = [key for key in ['sst_c', 'current_u', 'current_v', 'bait_score'] if key not in channels]
        if missing:
            raise SystemExit(f'missing ocean channel(s) from {url}: {missing}; channels={list(channels)}')
        status = data.get('status', {})
        contract = frame.get('metadata', {}).get('rtofs_tiled_contract') or status.get('details', {}).get('rtofs_tiled_contract') or {}
        print(json.dumps({
            'ok': True,
            'url': url,
            'provider': status.get('provider'),
            'status_ok': status.get('ok'),
            'live_ok': status.get('live_ok'),
            'degraded': status.get('degraded'),
            'depth_levels': frame.get('depth_levels'),
            'rtofs_tiled_contract': {
                'all_ocean_requests_tiled': contract.get('all_ocean_requests_tiled'),
                'no_whole_viewport_rtofs_call': contract.get('no_whole_viewport_rtofs_call'),
                'ocean_tile_count': contract.get('ocean_tile_count'),
                'parallelism': contract.get('parallelism'),
            },
        }))
        return

    msg = '\n'.join(errors) if errors else 'no URLs attempted'
    raise SystemExit(
        'Could not reach the LFTR backend for the RTOFS provider check.\n'
        f'Tried:\n{msg}\n\n'
        'Fix/check:\n'
        '  sudo systemctl status broadcast.service --no-pager -l\n'
        '  sudo systemctl restart broadcast.service\n'
        '  curl -sS http://127.0.0.1:8787/gfs/api/providers/status | jq .\n'
        'Or set BASE_URL explicitly if your backend uses another port.\n'
    )


if __name__ == '__main__':
    main()
