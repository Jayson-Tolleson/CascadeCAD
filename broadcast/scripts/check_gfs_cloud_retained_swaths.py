#!/usr/bin/env python3
from pathlib import Path

main = Path('frontend/src/main.ts').read_text()
google = Path('frontend/src/renderer/google3d.ts').read_text()
css = Path('frontend/src/styles/app.css').read_text()
particles = Path('frontend/src/renderer/cloudParticles.ts').read_text()

required_main = [
    "clouds: ['cloud-shapes', 'clouds']",
    'Cloud renderer retained last good',
    'CloudMorphController',
    "overlay.syncPolygons('cloud-shapes'",
    'Cloud persistent morph mode',
]
forbidden_main = ['cachedCloudFeatures = null;']
required_google = [
    'drawsOccludedSegments?: boolean',
    "altitudeMode: spec.altitudeMode ?? 'RELATIVE_TO_GROUND'",
    'marker.setAttribute(\'glyph\', spec.label ?? \'●\')',
]
required_css = [
    'cloud-particle-ellipsoid',
    'cloud-family-marker',
    'Cloud Render Pass 4',
]
required_particles = [
    'toShellPolygons',
    'toParticlePolygons',
    'CloudParticleGenerator',
]
missing = [item for item in required_main if item not in main]
missing += [f'forbidden main token still present: {item}' for item in forbidden_main if item in main]
missing += [item for item in required_google if item not in google]
missing += [item for item in required_css if item not in css]
missing += [item for item in required_particles if item not in particles]
if missing:
    raise SystemExit('Missing cloud retained/swath render markers:\n' + '\n'.join(missing))
print('✓ /gfs clouds retain last good, morph/advect persistent polygons, and render cloud bodies plus swaths')
