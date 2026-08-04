# Broadcast/Watch Route Contract

This is the required clean contract for future pass #9. Pass #9 implements these routes as the only broadcast/watch runtime surface.

## Final user surfaces

| Surface | Method | Path | Purpose |
| --- | --- | --- | --- |
| Broadcaster page | `GET` | `/broadcast` | One responsive broadcaster UI for mobile and desktop. |
| Watch page | `GET` | `/watch` | One responsive viewer UI for mobile and desktop. |
| Status | `GET` | `/api/broadcast/status` | Optional diagnostics/status without secrets. |

## Final WebSockets

| Socket | Path | Purpose |
| --- | --- | --- |
| Broadcast signaling | `/ws/broadcast` | Broadcaster presence, WebRTC offers/answers/ICE, media state. |
| Watch signaling | `/ws/watch` | Viewer presence, WebRTC offers/answers/ICE, playback state. |
| Chat | `/ws/chat` | Text chat, STT transcript events, AI bridge replies, attachments, web-search results. |

## Message families to preserve

- `presence`: broadcaster connected, viewer count, room state.
- `signaling`: offer, answer, ICE candidate, renegotiation diagnostics.
- `chat`: user text, broadcaster text, watcher text, system notices.
- `stt`: chunk accepted/rejected, final transcript, retry/backoff status.
- `ai`: reply text, optional voice payload hook, status/error events.
- `upload`: image attachment metadata and optional media-upload status.
- `debug`: browser permission, media device, WebRTC, and socket status.

## Forbidden route sprawl

Future implementation must not add:

- `/broadcast2`
- `/watch2`
- old GFS-prefixed broadcaster aliases
- mixed broadcast/globe route aliases
- duplicate chat socket paths
- duplicate media loops

## Minimal status response sketch

```json
{
  "ok": true,
  "enabled": true,
  "rooms": 1,
  "routes": ["/broadcast", "/watch"],
  "websockets": ["/ws/broadcast", "/ws/watch", "/ws/chat"],
  "degraded": false
}
```

The status endpoint must not reveal credentials, room secrets, upload paths outside public URLs, API keys, or database DSNs.

## Broadcast pill finish contract

The `/broadcast` surface now keeps a deliberately small pill set:

- `Facing` — switches camera facing mode between front/user and back/environment.
- `SCREEN compositor` — starts screen sharing and composites the camera as a lower-right overlay with green, blue, and orange borders.
- `STT` — browser SpeechRecognition hook; sends final transcripts into chat when supported by the browser.
- `AI bridge` — visible placeholder/request hook. Vertex runtime is not connected yet and must not crash the app.
- `AI voice` — visible option toggle for future voice monitor/output behavior.
- `Record` — one press starts recording the active camera/compositor stream; the next press stops and automatically downloads a `.webm` file.
- `RTMP` — staged placeholder/hook for future outbound RTMP integration.

Removed from the UI by design:

- manual `CAM on` pill; camera now auto-starts so permissions pop on page load.
- manual `MIC on/off` pill; audio is part of camera/compositor capture.
- `NoiseCancel` pill; browser capture constraints request echo/noise handling quietly.
- separate `Download` pill; download is part of the Record stop action.
