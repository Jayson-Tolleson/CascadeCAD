#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
checks = {
    'scripts/install.sh': ['python3-pydantic', 'python3-pydantic-settings', 'Optional apt pydantic packages'],
    'app/providers/provider_status.py': ['def ok(self) -> bool', 'computed_field'],
    'scripts/check_rtofs_provider.py': ['/etc/broadcast/install.env', 'APP_PORT', 'http://127.0.0.1:8787', 'status_ok'],
    'docs/installer_apt_pydantic_provider_status.md': ['ProviderStatus', 'python3-pydantic-settings'],
}
for rel, needles in checks.items():
    text = (ROOT / rel).read_text()
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f'{rel} missing {missing}')
print('✓ installer apt pydantic + provider status compatibility checks passed')
