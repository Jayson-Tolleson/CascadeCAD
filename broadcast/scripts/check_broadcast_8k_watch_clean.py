from pathlib import Path
root = Path(__file__).resolve().parents[1]
media = (root / 'frontend/src/broadcast/media.ts').read_text()
watch = (root / 'frontend/src/broadcast/watchApp.ts').read_text()
broadcast_app = (root / 'frontend/src/broadcast/broadcastApp.ts').read_text()
required = ['7680', '4320', '3840', '2160', '2560', '1440', '4032', '3040', 'maintain-resolution']
missing = [token for token in required if token not in (media + broadcast_app)]
assert not missing, f'missing 8k/4k/2k stream-ladder tokens: {missing}'
assert 'href="/broadcast"' not in watch, 'watch page still has Go /broadcast pill/link'
assert 'Go /broadcast' not in watch, 'watch page still has Go /broadcast text'
assert 'SIZE <b id="streamSize"' in watch, 'watch stream size diagnostic was removed unexpectedly'
assert 'PROFILE <b id="streamProfile"' in watch, 'watch stream profile diagnostic was removed unexpectedly'
print('ok: broadcast_8k_watch_clean')
