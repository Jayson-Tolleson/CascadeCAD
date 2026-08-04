# LFTR Broadcast/Watch Migration Plan

This document was the clean-room plan for pass #9 and remains the guardrail for the implemented compact runtime. Pass #9 intentionally enables only `/broadcast`, `/watch`, `/ws/broadcast`, `/ws/watch`, `/ws/chat`, and `/api/broadcast/status`.

## Current boundary

LFTR Next remains the compact marine intelligence app:

- GFS/RTOFS provider adapters feed field-truth contracts.
- PostGIS/USGS spatial modules feed stable place-truth contracts.
- The TypeScript globe renderer is not loaded by broadcast/watch pages by default.
- Broadcast/watch will be a separate user surface with minimal shared helpers only.

## Legacy audit summary

The available legacy archive is `LFTR-Broadcast-GFS-Marine-Globe-current-field-bridge-patch.zip`. It was inspected as read-only reference; no legacy code was copied into `lftr-next`.

Observed legacy behavior to preserve conceptually:

- Broadcast and watch surfaces existed alongside marine/GFS paths.
- WebSockets were separated by purpose: chat, broadcaster signaling, and watcher signaling.
- Chat carried normal text, STT transcript messages, attachment notifications, AI replies, and web-search results.
- Media behavior included camera broadcast, viewer playback, recording/RTMP hooks, and upload fallback hooks.
- WebRTC/signaling behavior included offer, answer, ICE candidate, broadcaster presence, viewer count, and room state messages.
- STT behavior included chunk status, retry/backoff, and final-transcript handoff to chat/AI.
- AI bridge behavior generated text replies and optionally voice/TTS payloads.
- Image/upload behavior supported chat attachments and media upload status.
- Browser behavior differed between Chrome and Firefox, especially for STT, autoplay, camera facing mode, and permissions.

Legacy behavior to discard:

- Large monolithic route files and giant frontend scripts.
- Mixed GFS/globe concerns inside broadcast/watch runtime code.
- Duplicate page routes, duplicate socket paths, and alias route sprawl.
- Duplicate overlay video loops and duplicated chat socket handling.
- “Speak last AI” clutter unless a future pass explicitly re-enables it.

## Future #9 backend module plan

Future work should add small modules only:

- `app/broadcast/routes.py`
- `app/broadcast/rooms.py`
- `app/broadcast/messages.py`
- `app/broadcast/signaling.py`
- `app/broadcast/uploads.py`
- `app/broadcast/sanitize.py`
- `app/broadcast/status.py`
- `app/api/routes_broadcast.py`

## Future #9 frontend module plan

Future work should add focused frontend modules only:

- `frontend/src/broadcast/broadcastApp.ts`
- `frontend/src/broadcast/watchApp.ts`
- `frontend/src/broadcast/chat.ts`
- `frontend/src/broadcast/media.ts`
- `frontend/src/broadcast/signaling.ts`
- `frontend/src/broadcast/stt.ts`
- `frontend/src/broadcast/uploads.ts`
- `frontend/src/broadcast/webSearchPane.ts`
- `frontend/src/styles/broadcast.css`

## Future broadcast page behavior

The future `/broadcast` page should support:

- One mobile/desktop page.
- Camera start/stop.
- Front/back camera switching.
- Microphone selection.
- STT hook.
- Broadcaster chat.
- AI bridge hook.
- Upload hook if needed.
- Debug/status panel.
- No GFS renderer loaded by default.

## Future watch page behavior

The future `/watch` page should support:

- One mobile/desktop page.
- Autoplay/watch video path with browser-policy handling.
- Collapsible right-side chat.
- Image upload in chat.
- Web/search pane hook where allowed.
- Enter-to-send.
- Debug/status panel.
- No small duplicate overlay video unless explicitly requested.
- No GFS renderer loaded by default.

## Separation rules

Broadcast/watch must not import the globe renderer by default. The globe app must not import broadcast scripts. Shared code should stay limited to:

- WebSocket helper.
- Chat sanitizer.
- Upload helper.
- Status panel helper.

## Pass #9 runtime status

The runtime now implements the minimal broadcast/watch contract with tests proving no duplicate route aliases, no duplicate socket loops, and no globe renderer dependency on broadcast pages. Future passes may add real uploads, server-side AI integrations, and production WebRTC media handling without changing the route contract.
