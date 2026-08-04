from fastapi import APIRouter
from app.schemas.scene import SceneSnapshot
from app.services.scene_snapshot import build_scene_snapshot

router = APIRouter(prefix="/gfs/api", tags=["scene"])


@router.get("/scene-frame", response_model=SceneSnapshot)
def scene_frame() -> dict:
    return build_scene_snapshot()
