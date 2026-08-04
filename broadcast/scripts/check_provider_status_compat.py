#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _venv_bootstrap import reexec_into_project_venv
    reexec_into_project_venv(ROOT)
except Exception:
    pass

from app.providers.provider_status import ProviderStatus, now_iso

status = ProviderStatus(provider='test', mode='live', enabled=True, live_ok=True, generated_time=now_iso())
assert status.ok is True
payload = status.model_dump(mode='json')
assert payload.get('ok') is True
print({'ok': True, 'check': 'provider_status_ok_compat', 'payload_ok': payload.get('ok')})
