from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["site"])


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"


SITE_HTML = """<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>LFTR.biz</title>
<style>
body{margin:0;font-family:'Trebuchet MS',Arial,sans-serif;background:#1339de;color:white}.titlebar{text-align:center;padding:18px 14px;background:#0f2fb5;box-shadow:0 8px 22px rgba(0,0,0,.22)}h1{margin:0;font-size:clamp(2rem,5vw,3.8rem);letter-spacing:.03em}.home{padding-bottom:22px}.frame{margin:20px;background:#000;border-radius:12px;overflow:hidden;box-shadow:0 0 20px rgba(0,0,0,.4)}iframe{width:100%;border:0;display:block;background:#000}.watch-frame{aspect-ratio:16/9}.watch-frame iframe{height:100%}.globe-frame iframe{height:min(76vh,800px);min-height:520px}.youtube-frame iframe{height:520px}@media(max-width:768px){.frame{margin:12px}.globe-frame iframe,.youtube-frame iframe{height:420px;min-height:0}}
</style>
</head>
<body>
<main class=\"home\">
<header class=\"titlebar\"><h1>LFTR.biz</h1></header>
<section class=\"frame watch-frame\"><iframe src=\"/watch\" title=\"LFTR Watch\" allow=\"autoplay; fullscreen; picture-in-picture; camera; microphone\"></iframe></section>
<section class=\"frame globe-frame\"><iframe src=\"/gfs\" title=\"LFTR Marine Intelligence Globe\" allow=\"fullscreen; geolocation\"></iframe></section>
<section class=\"frame youtube-frame\"><iframe src=\"https://www.youtube.com/embed/videoseries?list=PLVIftPRSOIthwubkq9WzCSk7B-mqaJ89B\" title=\"LFTR YouTube playlist\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share\" allowfullscreen></iframe></section>
</main>
</body>
</html>"""


# Fallback only.  Production should serve frontend/dist/index.html, whose script
# points to /assets/gfs-*.js.  The old backend /gfs HTML pointed at /src/main.ts,
# which is a Vite-dev path and caused a globe/page shell with no layer runtime
# whenever the backend route was hit directly.
GFS_FALLBACK_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>LFTR Marine Intelligence Globe</title>
  <script async src=\"https://maps.googleapis.com/maps/api/js?key=%VITE_GOOGLE_MAPS_API_KEY%&v=alpha&libraries=maps3d\"></script>
</head>
<body>
  <div id=\"app\"></div>
  <div style=\"position:fixed;inset:auto 16px 16px 16px;z-index:99;padding:12px;border:1px solid rgba(125,211,252,.4);border-radius:14px;background:rgba(2,6,23,.82);color:#eaf7ff;font-family:system-ui\">
    Frontend build assets were not found. Run <code>cd frontend && npm install && npm run build</code> or reinstall with frontend build enabled.
  </div>
</body>
</html>"""


def _dist_html(name: str, fallback: str) -> str:
    path = DIST / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


@router.get("/")
async def get_site_index():
    return HTMLResponse(_dist_html("site.html", SITE_HTML))


@router.get("/gfs")
async def get_gfs_page():
    return HTMLResponse(_dist_html("index.html", GFS_FALLBACK_HTML))
