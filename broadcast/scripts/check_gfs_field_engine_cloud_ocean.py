#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
files = {
    'scalar': root / 'app/fields/scalar.py',
    'atmosphere': root / 'app/fields/atmosphere.py',
    'ocean': root / 'app/fields/ocean.py',
    'cloud_features': root / 'app/services/cloud_features.py',
    'ocean_features': root / 'app/services/ocean_features.py',
    'field_truth': root / 'app/services/field_truth_engine.py',
    'stream_bus': root / 'app/services/stream_bus.py',
    'main': root / 'frontend/src/main.ts',
    'stream': root / 'frontend/src/api/stream.ts',
    'config': root / 'app/core/config.py',
}
text = {name: path.read_text() for name, path in files.items()}
checks = {
    'xyz scalar primitives': all(x in text['scalar'] for x in ['class ScalarField2D', 'def bilinear', 'class ScalarField3D', 'def trilinear', 'parse_depth_levels_m']),
    'dense atmosphere grid': '(64, 64)' in text['atmosphere'] and 'low_cloud' in text['atmosphere'] and 'high_cloud' in text['atmosphere'],
    'ocean xyz depth engine': all(x in text['ocean'] for x in ['build_mock_ocean_volume', 'sample_mock_ocean', 'depth_m_positive_down', 'bait_depth_m', 'bathymetry_m']),
    'cloud feature extractor': all(x in text['cloud_features'] for x in ['extract_cloud_features', 'components', 'marine-stratus', 'cumulonimbus']),
    'ocean feature extractor': all(x in text['ocean_features'] for x in ['extract_ocean_features', 'current_vectors', 'bait_clusters']),
    'stream emits features': all(x in text['stream_bus'] for x in ['cloud.features.patch', 'ocean.features.patch']),
    'engine exposes feature patches': all(x in text['field_truth'] for x in ['cloud_features_patch', 'ocean_features_patch']),
    'frontend consumes cloud features': all(x in text['main'] for x in ['CloudFeaturesPayload', 'cloudFeatureMarkers', "event.type === 'cloud.features.patch'"]),
    'frontend stream knows feature events': all(x in text['stream'] for x in ['cloud.features.patch', 'ocean.features.patch']),
    'config exposes budgets': all(x in text['config'] for x in ['field_engine_grid_size', 'cloud_feature_threshold', 'ocean_bait_threshold']),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print('Field engine cloud/ocean check failed: ' + ', '.join(failed), file=sys.stderr)
    raise SystemExit(1)
print('✓ LFTR Field Engine Pass 1: dense cloud scalar features + ocean-compatible xyz/depth scalar engine')
