import json
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.services.stream_bus import field_truth_sse_events
from app.spatial.viewport_query import parse_bbox

router = APIRouter(tags=["stream"])


@router.get("/gfs/api/stream")
def stream(
    bbox: str | None = Query(None, description="optional minLon,minLat,maxLon,maxLat viewport bbox"),
    tier: str = Query("regional"),
    debug_raw: bool = Query(False, description="emit raw provider diagnostics instead of truth-safe renderer patches"),
) -> StreamingResponse:
    parsed = None
    if bbox:
        try:
            parsed = parse_bbox(bbox)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StreamingResponse(field_truth_sse_events(parsed, tier=tier, debug_raw=debug_raw), media_type="text/event-stream")


@router.websocket("/ws/gfs")
async def websocket_gfs(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json({"event": "scene.heartbeat", "ok": True, "transport": "websocket"})
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(json.dumps({"event": "echo", "data": message}))
    except WebSocketDisconnect:
        return
