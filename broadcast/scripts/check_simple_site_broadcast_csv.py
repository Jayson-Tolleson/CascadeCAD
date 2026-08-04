#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
site = (ROOT / 'frontend/src/site/siteApp.ts').read_text(encoding='utf-8')
broadcast = (ROOT / 'frontend/src/broadcast/broadcastApp.ts').read_text(encoding='utf-8')
watch = (ROOT / 'frontend/src/broadcast/watchApp.ts').read_text(encoding='utf-8')
reports = ROOT / 'data/reports.csv'
raw = ROOT / 'data/fishloclist.csv'
required_site = ['<h1>LFTR.biz</h1>', 'src="/watch"', 'src="/gfs"', 'youtube.com/embed/videoseries']
required_broadcast = ['facingBtn', 'screenBtn', 'sttBtn', 'aiEnableBtn', 'ttsMonBtn', 'recordBtn', 'rtmpBtn', 'Go /watch']
required_comm = ['RTCPeerConnection', 'watcher-ready', '/ws/broadcast']
required_watch = ['RTCPeerConnection', 'watcher-ready', '/ws/watch']
missing = []
for token in required_site:
    if token not in site:
        missing.append(f'site missing {token}')
for token in required_broadcast + required_comm:
    if token not in broadcast:
        missing.append(f'broadcast missing {token}')
for token in required_watch:
    if token not in watch:
        missing.append(f'watch missing {token}')
if not raw.exists():
    missing.append('data/fishloclist.csv missing')
if not reports.exists():
    missing.append('data/reports.csv missing')
else:
    with reports.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 20:
        missing.append(f'expected zippy reports, found {len(rows)}')
if missing:
    raise SystemExit(json.dumps({'ok': False, 'missing': missing}, indent=2))
print(json.dumps({'ok': True, 'site': 'simple zippy frames', 'reports': len(rows), 'broadcast_pills': 'finished simple pill set', 'webrtc_hooks': True}, indent=2))
