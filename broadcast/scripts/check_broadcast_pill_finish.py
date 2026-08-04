#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parents[1]
app = (root / 'frontend/src/broadcast/broadcastApp.ts').read_text()
media = (root / 'frontend/src/broadcast/media.ts').read_text()
css = (root / 'frontend/src/styles/broadcast.css').read_text()
errors = []
for forbidden in ['#camBtn', '#micBtn', '#ncBtn', 'id="download"']:
    if forbidden in app:
        errors.append(f'forbidden broadcast control still present: {forbidden}')
for required in ['#facingBtn', '#screenBtn', '#sttBtn', '#aiEnableBtn', '#ttsMonBtn', '#recordBtn', '#rtmpBtn']:
    if required not in app:
        errors.append(f'missing required pill: {required}')
for required in ['autoStartCamera', 'startScreenCompositor', 'toggleRecording', 'captureStream', 'drawComposite']:
    if required not in media and required not in app:
        errors.append(f'missing media behavior: {required}')
for required in ['cameraPermission', 'compositorStage', 'recordPill']:
    if required not in css and required not in app:
        errors.append(f'missing compositor/pill style marker: {required}')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print('broadcast pill finish checks passed')
