# `frontend/src/broadcast`

This directory contains the compact pass #9 broadcast/watch frontend runtime.

It intentionally does not import the globe renderer, field store, marine layer modules, Google map modules, or the globe scene API. The Vite entries are `broadcast.html` and `watch.html`.

Current files:

- `broadcastApp.ts` — broadcaster UI with camera, microphone, STT hook, chat, and placeholders.
- `watchApp.ts` — watcher UI with muted playback, collapsible chat, and placeholders.
- `chat.ts` — shared sanitized chat socket client.
- `media.ts` — browser camera/microphone helper.
- `signaling.ts` — small JSON WebSocket helper.
- `stt.ts` — browser STT capability hook.
- `uploads.ts` — disabled upload placeholder hook.
- `webSearchPane.ts` — disabled web/search placeholder hook.
