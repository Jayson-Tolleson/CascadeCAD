#!/usr/bin/env python3
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
pills = (root / 'frontend/src/ui/layerPills.ts').read_text()
g3d = (root / 'frontend/src/renderer/google3d.ts').read_text()
check = (root / 'scripts/check_gfs_viewport_data_intake.sh').read_text()
errors=[]
if "{ id: 'locations', label: 'Locations' }" not in pills or pills.index("{ id: 'locations', label: 'Locations' }") > pills.index("{ id: 'clouds', label: 'Clouds' }"):
    errors.append('Locations must be the leftmost/first pill')
if 'locationOrbPolygons' not in main or "syncPolygons('locations'" not in main:
    errors.append('Locations must render visible green polygon orbs')
if 'gmp-clickable' not in g3d or 'onClick?: () => void' not in g3d or 'Polygon3DElement' not in g3d:
    errors.append('Green polygon orbs must be explicitly clickable')
if 'first_location: .reports[0]' in check or 'sed -n' in check:
    errors.append('Viewport data intake check must not dump full CSV/SSE printouts')
if errors:
    print('FAIL')
    for e in errors: print('-', e)
    raise SystemExit(1)
print('PASS: locations first, green polygon orbs, concise printout checks are present')
