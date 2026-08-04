# Broadcast true camera resolution patch

This patch removes the old 1280x720/16:9 assumption from `/broadcast` and `/watch` and adds a high-resolution capture ladder up to 8K.

## What changed

- `/broadcast` now defaults to an 8K request: `7680x4320` landscape.
- The broadcaster UI has a **Stream size** selector:
  - `8K 16:9 7680x4320`
  - `8K portrait 4320x7680`
  - `TRUE 4:3 4032x3040`
  - `TRUE portrait 3040x4032`
  - `4K 16:9 3840x2160`
  - `4K portrait 2160x3840`
  - `2K/QHD 16:9 2560x1440`
  - `2K/QHD portrait 1440x2560`
  - `AUTO max sensor`
  - `SAFE 1280x720`
- High-resolution requests now use an ordered fallback ladder. For example, 8K landscape tries 8K first, then 4032x3040, then 4K, then 2K, then 720p.
- The capture code asks for `resizeMode: none` so browsers that support it avoid pre-cropping or pre-scaling the camera feed.
- The status line shows the actual granted browser stream size, for example `Stream: 7680x4320 @ 30fps`, `Stream: 3840x2160 @ 30fps`, or a lower fallback if the device/browser refuses the requested mode.
- WebRTC video senders request `degradationPreference: maintain-resolution`, `scaleResolutionDownBy = 1`, and a dynamic bitrate target:
  - 8K class: about 120 Mbps
  - 4032x3040 / 12MP class: about 60 Mbps
  - 4K class: about 45 Mbps
  - 2K/QHD class: about 24 Mbps
  - 1080p class: about 12 Mbps
  - 720p class: about 6 Mbps
- MediaRecorder now uses the same dynamic bitrate ladder for local WebM recording instead of the old fixed 28 Mbps target.
- The screen compositor no longer forces a `1280x720` canvas. It sizes itself from the screen stream and draws screen/camera using aspect-preserving containment.
- `/watch` shows a **SIZE** badge based on the actual received stream/video dimensions and a **PROFILE** badge showing requested vs granted profile.
- The home-page `/watch` iframe is no longer locked to `aspect-ratio: 16 / 9`.

## Important browser reality

8K live WebRTC is an aggressive request. A camera may support 8K still photos but not expose an 8K live video mode through `getUserMedia()`. Even when the camera grants 8K, the browser encoder, GPU, CPU, network, TURN/STUN path, and the viewer device may still downshift or fail.

This patch asks for 8K first and falls back gracefully. The green status readout and the `/watch` SIZE/PROFILE badges are the source of truth for what the browser actually granted and what the viewer actually received.

For true full-sensor still-frame capture, a later patch can add `ImageCapture.takePhoto()` alongside the live stream.
