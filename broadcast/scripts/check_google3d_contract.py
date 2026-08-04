#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
index = (root / 'frontend/index.html').read_text()
google3d = (root / 'frontend/src/renderer/google3d.ts').read_text()
site = (root / 'frontend/src/site/siteApp.ts').read_text()
broadcast = (root / 'frontend/src/broadcast/broadcastApp.ts').read_text()
errors = []
checks = {
    'maps3d script': 'libraries=maps3d' in index,
    'google3d module': 'createGoogle3DMap' in main,
    'Map3DElement': 'Map3DElement' in google3d,
    'Marker3DElement': 'Marker3DElement' in google3d,
    'Polyline3DElement': 'Polyline3DElement' in google3d,
    'Polygon3DElement': 'Polygon3DElement' in google3d,
    'no fake visual-root in main': 'visualRoot' not in main,
    'no mock screen projection in main': 'translate3d' not in main,
    'simple site': 'preview-frame' not in site and 'iframe' not in site,
    'broadcast recording': 'startRecording' in broadcast and 'Download Recording' in broadcast,
    'watch link': '/watch' in site and '/watch' in broadcast,
}
for name, ok in checks.items():
    if not ok:
        errors.append(name)
if errors:
    raise SystemExit({'ok': False, 'failed': errors})
print({'ok': True, 'checks': sorted(checks)})
