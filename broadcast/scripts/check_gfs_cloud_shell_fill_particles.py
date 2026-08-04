#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
google = (root / 'frontend/src/renderer/google3d.ts').read_text()
recipes = (root / 'frontend/src/renderer/cloudRecipes.ts').read_text()
seed = (root / 'frontend/src/renderer/cloudSeed.ts').read_text()
particles = (root / 'frontend/src/renderer/cloudParticles.ts').read_text()
css = (root / 'frontend/src/styles/app.css').read_text()
backend = (root / 'app/services/cloud_features.py').read_text()

families = ['cumulus', 'stratus', 'cirrus', 'marine_stratus', 'cumulonimbus']
styles = ['puff_cluster', 'flat_sheet', 'wispy_streak', 'coastal_blanket', 'tower_stack']
checks = {
    'cloud particle generator exists': 'class CloudParticleGenerator' in particles and 'generateMany' in particles,
    'cloud particle renderer exists': 'class CloudParticleRenderer' in particles and 'toParticlePolygons' in particles,
    'cloud shell normalization exists': 'interface CloudShell' in particles and 'cloudShellFromFeature' in particles,
    'seeded PRNG/hash exists': 'hashStringToUint32' in seed and 'class SeededRandom' in seed and 'Mulberry32' in seed,
    'family recipes include all families': all(name in recipes for name in families),
    'family render styles include all styles': all(style in recipes for style in styles),
    'tier particle caps exist': all(token in recipes for token in ['global: 300', 'regional: 900', 'local: 1600']),
    'particle budgets exist': all(token in recipes for token in ['global: [', 'regional: [', 'local: [']),
    'backend stable seed fields': all(token in backend for token in ['_feature_digest', 'particle_seed', 'particle_budget', 'cells_per_particle', 'rain_factor']) and 'uuid4' not in backend,
    'google polygon supports cloud geometry': 'Polygon3DElement' in google and 'onClick?: () => void' in google and 'gmp-polygon-3d' in particles,
    'pass 4 css exists': all(token in css for token in ['Cloud Render Pass 4', 'lftr-cloud-pass4-breathe', 'lftr-cloud-pass4-drift']),
    'main uses pass 4 geometry renderer': 'buildCloudBodyRender' in main and ('Cloud renderer geometry mode' in main or 'Cloud persistent morph mode' in main) and "syncPolygons('clouds'" in main,
    'retained-last-good still exists': 'Cloud renderer retained last good' in main and 'CloudMorphController' in main and 'cachedCloudFeatures = null;' not in main,
    'clouds pill clears bodies': "clouds: ['cloud-shapes', 'clouds']" in main and "clearLayer('clouds')" in main,
    'old marker-only path is not active': 'toParticlePolygons' in particles and 'no-marker-cloud-fill' in particles and ("syncMarkers('clouds', [])" in main or "syncMarkers('clouds', cloudFeatureMarkers(null))" in main),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Cloud shell fill particle check failed: ' + ', '.join(failed))
print('✓ Cloud Render Pass 4 shell fill is wired as seeded gmp-polygon-3d geometry, not marker spheres')
