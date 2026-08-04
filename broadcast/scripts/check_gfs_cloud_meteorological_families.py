#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
google = (root / 'frontend/src/renderer/google3d.ts').read_text()
css = (root / 'frontend/src/styles/app.css').read_text()
cloud_features = (root / 'app/services/cloud_features.py').read_text()
recipes = (root / 'frontend/src/renderer/cloudRecipes.ts').read_text()
particles = (root / 'frontend/src/renderer/cloudParticles.ts').read_text()

families_hyphen = ['cumulus', 'stratus', 'cirrus', 'marine-stratus', 'cumulonimbus']
families_recipe = ['cumulus', 'stratus', 'cirrus', 'marine_stratus', 'cumulonimbus']
styles_hyphen = ['puff-cluster', 'flat-sheet', 'wispy-streak', 'coastal-blanket', 'tower-stack']
styles_recipe = ['puff_cluster', 'flat_sheet', 'wispy_streak', 'coastal_blanket', 'tower_stack']
checks = {
    'frontend cloud family names': all(name in (main + recipes + particles) for name in families_recipe),
    'backend cloud family names': all(name in cloud_features for name in families_hyphen),
    'render styles': all(style in (main + cloud_features) for style in styles_hyphen) and all(style in recipes for style in styles_recipe),
    'ellipsoid particles': all(token in particles for token in ['cloudFeatureParticleCount', 'cloudFeatureParticleOffset', 'cloud-particle-ellipsoid', 'CloudParticleGenerator']),
    'no cloud icon default': "spec.label ?? '●'" in google and "family === 'cirrus' ? '━'" in google,
    'custom ellipse template': all(token in google for token in ['cloud-ellipse-a', 'cloud-ellipse-shadow', '--cloud-color', '--cloud-glow']),
    'family CSS': all(f'.cloud-family-{name}' in css for name in families_hyphen),
    'wobble CSS': '@keyframes lftr-cloud-breathe' in css and '@keyframes lftr-cloud-pass4-breathe' in css,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Cloud meteorological family render check failed: ' + ', '.join(failed))
print('✓ /gfs cloud renderer uses meteorological families with seeded ellipsoid shell-fill particles')
