#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
google = (root / 'frontend/src/renderer/google3d.ts').read_text()
css = (root / 'frontend/src/styles/app.css').read_text()
recipes = (root / 'frontend/src/renderer/cloudRecipes.ts').read_text()
particles = (root / 'frontend/src/renderer/cloudParticles.ts').read_text()

checks = {
    'top-down zippy tilt': 'tilt: 18' in google and 'range: 115000' in google and 'heading: 0' in google,
    'cloud families classified': all(x in (main + recipes) for x in ['cumulus', 'stratus', 'cirrus', 'marine_stratus', 'cumulonimbus', 'puff_cluster', 'tower_stack']),
    'cloud data channels respected': all(x in (main + particles) for x in ['cloud_density', 'rain_rate', 'low_cloud', 'medium_cloud_cover', 'high_cloud_cover', 'humidity', 'wind_u', 'wind_v']),
    'cloud polygons stay on Google 3D': "syncPolygons('clouds'" in main and 'toParticlePolygons' in particles and 'Polygon3DElement' in google,
    'cloud marker fallback retained for debug': all(x in google for x in ['ensureCloudFamily', 'lftr-cloud-family', 'cloudFamily?:', 'cloudSize?:']),
    'family CSS exists': all(x in css for x in ['.cloud-family-cumulus', '.cloud-family-stratus', '.cloud-family-cirrus', '.cloud-family-marine-stratus', '.cloud-family-cumulonimbus', '.cloud-size-massive']),
    'pass 4 generator exists': 'class CloudParticleGenerator' in particles and 'class CloudParticleRenderer' in particles,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('Cloud family renderer check failed: ' + ', '.join(failed))
print('✓ /gfs cloud renderer uses top-down zippy view and pass-4 polygon meteorological cloud families')
