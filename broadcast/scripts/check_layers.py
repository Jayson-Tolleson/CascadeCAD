#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.layers.compiler import layer_status

status = layer_status()
expected = {'locations': 'spatial_points', 'clouds': 'field', 'rain': 'field', 'bait': 'scalar_field', 'boats': 'entity', 'shark-intel': 'event', 'inland-water': 'spatial', 'lightning': 'event'}
contracts = {item['id']: item for item in status['layers']}
for layer_id, kind in expected.items():
    if contracts[layer_id]['kind'] != kind:
        raise SystemExit(f'{layer_id} kind mismatch: {contracts[layer_id]["kind"]}')
    if 'budget' not in contracts[layer_id]:
        raise SystemExit(f'{layer_id} missing budget')
print(json.dumps({'ok': True, 'layers': list(contracts)}))
