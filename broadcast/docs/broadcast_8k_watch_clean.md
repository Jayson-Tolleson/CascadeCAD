# Broadcast 8K stream ladder + clean Watch header

This build keeps the Clouds/PostGIS `/gfs` work and keeps the `/broadcast` high-resolution camera ladder enabled.

## `/broadcast` stream profiles

The broadcast page can request these camera profiles and reports what the browser actually grants:

- 8K 16:9 — `7680×4320`
- 8K portrait — `4320×7680`
- TRUE 4:3 sensor — `4032×3040`
- TRUE portrait sensor — `3040×4032`
- 4K — `3840×2160`
- 4K portrait — `2160×3840`
- 2K/QHD — `2560×1440`
- 2K/QHD portrait — `1440×2560`
- AUTO max sensor
- SAFE 720p

The sender applies a dynamic bitrate/degradation preference so WebRTC tries to preserve resolution when the browser/network allows it.

## `/watch` header cleanup

The visible `/watch` header no longer includes the `Go /broadcast` pill/link. `/watch` remains a viewer page only, with stream state, size, and profile diagnostics still visible.
