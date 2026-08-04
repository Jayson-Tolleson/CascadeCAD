#!/usr/bin/env python3
"""Clouds pill: PostGIS-first, live-provider, no synthetic mock registration."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = (root / 'app/core/config.py').read_text()
env = (root / '.env.example').read_text()
compiler = (root / 'app/layers/compiler.py').read_text()
engine = (root / 'app/services/field_truth_engine.py').read_text()
repo = (root / 'app/prerender/postgis_repository.py').read_text()
routes_layers = (root / 'app/api/routes_layers.py').read_text()
routes_prerender = (root / 'app/api/routes_prerender.py').read_text()
frontend_clouds = (root / 'frontend/src/layers/clouds.ts').read_text()
main = (root / 'frontend/src/main.ts').read_text()
particles = (root / 'frontend/src/renderer/cloudParticles.ts').read_text()
requirements = (root / 'requirements.txt').read_text()
install = (root / 'scripts/install.sh').read_text()

checks = {
    'settings default postgis on': 'postgis_enabled: bool = True' in config and 'spatial_mode: str = "postgis"' in config,
    'settings default render cache on': 'render_cache_enabled: bool = True' in config,
    'env example postgis first': 'LFTR_POSTGIS_ENABLED="true"' in env and 'LFTR_RENDER_CACHE_ENABLED="true"' in env and 'LFTR_SPATIAL_MODE="postgis"' in env,
    'psycopg default dependency': 'psycopg[binary]' in requirements,
    'installer configures local postgis': 'configure_local_postgis()' in install and 'postgresql postgresql-contrib postgis' in install,
    'cloud layer contract uses feature patch': "cloud.features.patch" in compiler and 'postgis.cloud_render_features' in compiler,
    'cloud API route exists': "@router.get('/clouds')" in routes_layers and 'cloud_features_patch' in routes_layers,
    'cloud prerender route exists': '@router.post("/clouds")' in routes_prerender and 'precompute_cloud_render_features' in routes_prerender,
    'engine reads postgis then live fallback': 'postgis_cache_error' in engine and 'cache.cloud_hit' in engine and 'miss_live_generated' in engine,
    'engine writes through clouds': 'cache.write_cloud(payload)' in engine and 'layer": "clouds"' in engine,
    'repo stores live-provider policy': '_lftr_source_policy' in repo and 'source_kind != "live_provider"' in repo and '_lftr_pill' in repo,
    'frontend cloud registration is not mock': 'mock: false' in frontend_clouds and 'mock-clouds' not in frontend_clouds,
    'frontend renders cloud polygons': ('Cloud renderer geometry mode' in main or 'Cloud persistent morph mode' in main) and 'syncPolygons(\'clouds\'' in main and ('syncMarkers(\'clouds\', cloudFeatureMarkers(null))' in main or "syncMarkers('clouds', [])" in main),
    'particle polygon renderer exists': 'toParticlePolygons' in particles and 'gmp-polygon-3d' in particles and 'no-marker-cloud-fill' in particles,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit({'ok': False, 'check': 'gfs_cloud_postgis_live_contract', 'failed': failed})
print({'ok': True, 'check': 'gfs_cloud_postgis_live_contract', 'checks': len(checks)})
