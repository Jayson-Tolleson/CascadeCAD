from pathlib import Path
root = Path(__file__).resolve().parents[1]
media = (root / 'frontend/src/broadcast/media.ts').read_text()
app = (root / 'frontend/src/broadcast/broadcastApp.ts').read_text()
dist = ''.join(p.read_text(errors='ignore') for p in (root / 'frontend/dist/assets').glob('broadcast-*.js'))
required_media = [
    "private activeProfileKey: CameraProfileKey = 'auto-sensor'",
    'getCapabilities',
    'applyConstraints',
    'pushCameraToSensorMax',
    'safe-1080p',
    'chooseCompositeOutputSize',
    'cameraSettings()',
    'sensorMaxSummary()',
]
missing = [token for token in required_media if token not in media]
assert not missing, f'missing max-sensor source tokens: {missing}'
required_app = ['Output:', 'Camera:', 'sensor_max', 'camera_settings']
missing_app = [token for token in required_app if token not in app]
assert not missing_app, f'missing broadcast diagnostics tokens: {missing_app}'
required_dist = ['AUTO max sensor', 'sensor max:', 'SAFE 1920×1080']
missing_dist = [token for token in required_dist if token not in dist]
assert not missing_dist, f'built dist missing tokens: {missing_dist}'
print('ok: broadcast_max_sensor_start')
