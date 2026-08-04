from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api.routes_site import router as site_router
from app.api.routes_health import router as health_router
from app.api.routes_scene import router as scene_router
from app.api.routes_stream import router as stream_router
from app.api.routes_spatial import router as spatial_router
from app.api.routes_providers import router as providers_router
from app.api.routes_admin_spatial import router as admin_spatial_router
from app.api.routes_layers import router as layers_router
from app.api.routes_broadcast import router as broadcast_router
from app.api.routes_prerender import router as prerender_router
from app.core.config import get_settings
from app.core.logging import configure_logging

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(site_router)
    app.include_router(health_router)
    app.include_router(scene_router)
    app.include_router(stream_router)
    app.include_router(spatial_router)
    app.include_router(providers_router)
    app.include_router(admin_spatial_router)
    app.include_router(layers_router)
    app.include_router(broadcast_router)
    app.include_router(prerender_router)

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")
    models_dir = FRONTEND_DIST / "models"
    if models_dir.exists():
        app.mount("/models", StaticFiles(directory=str(models_dir)), name="frontend-models")
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
