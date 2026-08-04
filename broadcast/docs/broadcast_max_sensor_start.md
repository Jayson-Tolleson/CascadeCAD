# Broadcast max-sensor camera start patch

This patch fixes the case where `/broadcast` asked for a high resolution with `ideal` constraints, but Chrome silently granted 1080p and the app accepted that as the final camera mode.

## What changed

- `/broadcast` now defaults to **AUTO max sensor** instead of a fixed 16:9 8K request.
- The AUTO path opens the camera, reads `MediaStreamTrack.getCapabilities()`, and tries to push the live camera track to the largest exposed sensor mode with `applyConstraints()`.
- Explicit high-resolution choices now use strict size probing in the fallback ladder. For example, 8K does not silently accept 1080p as success; it falls through to 12MP/4K/2K/1080p/720p as needed.
- Added a **SAFE 1920×1080** fallback before 720p so normal HD cameras still get the best standard mode.
- The broadcaster status now separates:
  - **Output** stream size
  - **Camera** capture size
  - **Sensor max** reported by browser capabilities
- `media-state` sent to `/watch` now includes `camera_settings` and `sensor_max` for diagnostics.
- The screen compositor no longer lets a 1080p monitor cap the whole broadcast when the camera is larger. If the camera live sensor mode is bigger than the screen capture, the canvas output stays at the camera size and the screen is drawn into that larger output.

## Why this matters

A 1080p laptop display should not decide the camera stream resolution. The output stream and the camera sensor capture are separate things. This patch keeps them separate and gives the camera the first chance to run at its maximum live mode.

## Browser reality

The browser can only grant live video modes exposed by the camera driver. A camera may advertise high still-photo resolution but only expose 720p or 1080p as live video through `getUserMedia()`.

The `/broadcast` green status line is the source of truth:

```text
Output: 3840×2160 @ 30fps | Camera: 3840×2160 @ 30fps | sensor max: 3840×2160 @ ≤30fps
```

If it says:

```text
Camera: 1920×1080 | sensor max: 1920×1080
```

then the browser/driver is only exposing 1080p live camera video, regardless of the screen resolution.
