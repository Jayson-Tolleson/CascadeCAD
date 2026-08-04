from fastapi import APIRouter, WebSocket

from app.broadcast.routes import broadcast_page, broadcast_socket, chat_socket, status_payload, stt_socket, watch_page, watch_socket

router = APIRouter()


@router.get("/broadcast")
async def get_broadcast_page():
    return broadcast_page()


@router.get("/watch")
async def get_watch_page():
    return watch_page()


@router.get("/api/broadcast/status")
async def get_broadcast_status():
    return status_payload()


@router.websocket("/ws/broadcast")
async def websocket_broadcast(websocket: WebSocket):
    await broadcast_socket(websocket)


@router.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket):
    await watch_socket(websocket)


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await chat_socket(websocket)


@router.websocket("/ws/stt")
async def websocket_stt(websocket: WebSocket):
    await stt_socket(websocket)
