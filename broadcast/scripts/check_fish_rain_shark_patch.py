#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parents[1]
main = (root / 'frontend/src/main.ts').read_text()
pills = (root / 'frontend/src/ui/layerPills.ts').read_text()
pane = (root / 'frontend/src/ui/intelligencePane.ts').read_text()
compiler = (root / 'app/layers/compiler.py').read_text()
checks = {
    'location interactive marker overlay': "function locationOrbMarkers" in main and "template: 'green-orb'" in main and "location-hit-target" in main,
    'CSV glass pane selectReport': 'selectReport(report)' in pane and 'location-field-list' in pane and "report.latitude.toFixed(5)" in pane,
    'rain falling renderer': 'function rainDropLines' in main and 'rainColorForIntensity' in main and 'cloud top' in main and 'window.setInterval' in main,
    'ocean pill removed frontend': "{ id: 'ocean'" not in pills and "label: 'Ocean'" not in pills,
    'shark pill frontend': "{ id: 'shark-intel', label: 'Shark Intel' }" in pills and 'drawSharkIntel' in main,
    'ocean pill removed backend': "id='ocean'" not in compiler and "label='Ocean'" not in compiler,
    'shark contract backend': "id='shark-intel'" in compiler and "csv shark mentions + ocean_truth" in compiler,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise SystemExit('Patch contract failed: ' + ', '.join(missing))
print('✓ fish locations clickable, rain falling renderer wired, Ocean pill removed, Shark Intel pill added')
