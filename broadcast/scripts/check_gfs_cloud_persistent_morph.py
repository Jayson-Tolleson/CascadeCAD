#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
morph = (root / 'frontend/src/renderer/cloudMorph.ts').read_text()
particles = (root / 'frontend/src/renderer/cloudParticles.ts').read_text()
google = (root / 'frontend/src/renderer/google3d.ts').read_text()

checks = {
    'morph controller exists': 'class CloudMorphController' in morph and 'updateTarget' in morph and 'frame(' in morph,
    'retains missing bodies': 'missingSinceMs' in morph and 'holdMs' in morph and 'fadeOutMs' in morph,
    'advects with wind': 'advectPath' in morph and 'advectU' in morph and 'advectV' in morph,
    'morphs paths': 'interpolatePath' in morph and 'morphSeconds' in morph,
    'alpha fade rgba': 'multiplyRgbaAlpha' in morph and 'fadeSpec' in morph,
    'main wires morph': 'new CloudMorphController()' in main and 'updateCloudTargets' in main and 'ensureCloudMorphAnimation' in main,
    'does not reset cached clouds on reconnect': 'cachedCloudFeatures = null;' not in main and 'Do not clear cached cloud features here' in main,
    'cloud particles carry wind': 'spec.advectU = shell.windU' in particles and 'spec.advectV = shell.windV' in particles,
    'polygon spec supports wind': 'advectU?: number' in google and 'advectV?: number' in google,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit({'ok': False, 'check': 'gfs_cloud_persistent_morph', 'failed': failed})
print({'ok': True, 'check': 'gfs_cloud_persistent_morph', 'checks': len(checks)})
