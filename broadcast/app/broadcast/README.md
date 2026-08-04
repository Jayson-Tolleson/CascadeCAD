# `app.broadcast`

This package contains the compact pass #9 broadcast/watch runtime. It follows `docs/broadcast_migration_plan.md` and keeps broadcast/watch separate from GFS field-truth and globe-renderer modules.

Runtime routes are registered through `app/api/routes_broadcast.py` only:

- `GET /broadcast`
- `GET /watch`
- `GET /api/broadcast/status`
- `WS /ws/broadcast`
- `WS /ws/watch`
- `WS /ws/chat`

Current modules:

- `routes.py` — FastAPI handlers and lightweight HTML shells.
- `rooms.py` — in-memory room, broadcaster, watcher, and chat subscriber state.
- `messages.py` — message families and envelopes.
- `signaling.py` — bounded broadcaster/watcher signaling relay.
- `uploads.py` — upload placeholder status only; no file endpoint by default.
- `sanitize.py` — room, message type, display-name, and text sanitization.
- `status.py` — safe status payloads without secrets.
