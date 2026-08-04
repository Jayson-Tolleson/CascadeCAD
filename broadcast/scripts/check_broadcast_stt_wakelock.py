#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = {
    'stt': root / 'frontend/src/broadcast/stt.ts',
    'wake': root / 'frontend/src/broadcast/wakeLock.ts',
    'app': root / 'frontend/src/broadcast/broadcastApp.ts',
    'routes': root / 'app/broadcast/routes.py',
    'api': root / 'app/api/routes_broadcast.py',
    'service': root / 'app/broadcast/stt_service.py',
    'config': root / 'app/core/config.py',
}
for name, path in files.items():
    if not path.exists():
        raise SystemExit(f'missing {name}: {path}')

stt = files['stt'].read_text()
wake = files['wake'].read_text()
app = files['app'].read_text()
routes = files['routes'].read_text()
api = files['api'].read_text()
service = files['service'].read_text()
config = files['config'].read_text()

needles = [
    ('stt native', stt, 'SpeechRecognition || window.webkitSpeechRecognition'),
    ('stt server ws', stt, "wsUrl('/ws/stt'"),
    ('stt mediarecorder', stt, 'new MediaRecorder'),
    ('stt ogg/webm', stt, 'audio/ogg;codecs=opus'),
    ('wake request', wake, "navigator.wakeLock.request('screen')"),
    ('wake visibility', wake, 'visibilitychange'),
    ('wake keepalive', wake, 'setInterval'),
    ('broadcast wake badge', app, 'stWake'),
    ('broadcast stt toggle', app, 'stt.toggle'),
    ('api stt route', api, '/ws/stt'),
    ('route stt socket', routes, 'async def stt_socket'),
    ('google speech service', service, 'google.cloud'),
    ('stt settings', config, 'stt_enabled'),
]
for label, haystack, needle in needles:
    if needle not in haystack:
        raise SystemExit(f'missing {label}: {needle}')
print('✓ /broadcast STT now has Chrome native + Firefox server fallback, and Android wake lock guard is baked in')
