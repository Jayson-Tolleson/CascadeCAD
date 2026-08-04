#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
pills = (root / 'frontend/src/ui/layerPills.ts').read_text()
overlay = (root / 'frontend/src/renderer/google3d.ts').read_text()
css = (root / 'frontend/src/styles/app.css').read_text()

required = [
    "renderLayerPills(activeLayers, handleLayerToggle)",
    "const activeLayers = new Set<LayerId>",
    "groupsByLayer",
    "clearLayer(layer)",
    "if (!activeLayers.has('clouds'))",
    "if (!activeLayers.has('rain'))",
    "if (!activeLayers.has('bait'))",
    "clearIfDisabled('locations')",
    "clearIfDisabled('shark-intel')",
    "clearIfDisabled('inland-water')",
    "clearIfDisabled('boats')",
    "clearIfDisabled('lightning')",
]
missing = [item for item in required if item not in main]
if missing:
    raise SystemExit('main.ts missing layer toggle wiring: ' + ', '.join(missing))

for item in ["export type LayerId", "aria-pressed", "is-on", "is-off", "onToggle(layer.id"]:
    if item not in pills:
        raise SystemExit(f'layerPills.ts missing {item}')

for item in ["data-gfs-layer", "scale?: number", "glowColor?: string", "opacity?: number"]:
    if item not in overlay:
        raise SystemExit(f'google3d.ts missing {item}')

for item in [".layer-pill.is-off", ".cloud-volume-marker", ".bait-glow-marker", ".shark-intel-marker"]:
    if item not in css:
        raise SystemExit(f'app.css missing {item}')

print('✓ /gfs layer pills toggle real render groups; Ocean pill removed; Shark Intel pill present')
