from __future__ import annotations

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
import asyncio
from fastapi.responses import HTMLResponse

from app.broadcast.messages import envelope, system
from app.broadcast.rooms import room_manager
from app.broadcast.sanitize import clean_display_name, clean_payload, clean_room, clean_text
from app.broadcast.signaling import from_broadcaster, from_watcher
from app.broadcast.status import broadcast_status
from app.broadcast.stt_service import SttConfig, SttUnavailable, provider_status as stt_provider_status, transcribe_audio_chunk
from app.broadcast.uploads import upload_placeholder_status


def page_html(kind: str) -> str:
    title = "LFTR Broadcast" if kind == "broadcast" else "LFTR Watch"
    script = "/src/broadcast/broadcastApp.ts" if kind == "broadcast" else "/src/broadcast/watchApp.ts"
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{title}</title></head>
<body><div id=\"broadcast-app\" data-mode=\"{kind}\"><h1>{title}</h1><p>Clean LFTR {kind} runtime shell.</p></div><script type=\"module\" src=\"{script}\"></script></body></html>"""


def broadcast_page() -> HTMLResponse:
    return HTMLResponse(page_html("broadcast"))


def watch_page() -> HTMLResponse:
    return HTMLResponse(page_html("watch"))


def status_payload() -> dict:
    payload = broadcast_status()
    payload["uploads"] = upload_placeholder_status()
    payload["stt"] = stt_provider_status()
    return payload


async def broadcast_socket(ws: WebSocket) -> None:
    await ws.accept()
    room_id = clean_room(ws.query_params.get("room"))
    client_id = f"broadcast:{id(ws)}"
    room = await room_manager.register_broadcaster(room_id, client_id, ws)
    await room_manager.send(ws, system(room_id, "broadcaster connected"))
    try:
        while True:
            payload = clean_payload(await ws.receive_json())
            if payload.get("type") == "debug":
                await room_manager.send(ws, envelope("debug", room_id, {"type": "debug", "ok": True, "echo": payload}))
            else:
                await from_broadcaster(room, payload)
    except WebSocketDisconnect:
        await room_manager.unregister(room_id, client_id, "broadcast")


async def watch_socket(ws: WebSocket) -> None:
    await ws.accept()
    room_id = clean_room(ws.query_params.get("room"))
    client_id = f"watch:{id(ws)}"
    room = await room_manager.register_watcher(room_id, client_id, ws)
    await room_manager.send(ws, system(room_id, "watcher connected"))
    try:
        while True:
            payload = clean_payload(await ws.receive_json())
            await from_watcher(room, client_id, payload)
    except WebSocketDisconnect:
        await room_manager.unregister(room_id, client_id, "watch")


async def chat_socket(ws: WebSocket) -> None:
    await ws.accept()
    room_id = clean_room(ws.query_params.get("room"))
    client_id = f"chat:{id(ws)}"
    await room_manager.register_chat(room_id, client_id, ws)
    await room_manager.send(ws, system(room_id, "chat connected"))
    try:
        while True:
            payload = clean_payload(await ws.receive_json())
            kind = payload.get("type", "chat")
            name = clean_display_name(payload.get("name"))
            if kind == "chat":
                text = clean_text(payload.get("text"))
                if not text:
                    await room_manager.send(ws, envelope("system", room_id, {"type": "error", "error": "empty chat message"}))
                    continue
                await room_manager.broadcast_chat(room_id, envelope("chat", room_id, {"type": "chat", "client_id": client_id, "name": name, "text": text}))
            elif kind == "stt":
                await room_manager.broadcast_chat(room_id, envelope("stt", room_id, {"type": "stt", "client_id": client_id, "name": name, "text": clean_text(payload.get("text")), "final": bool(payload.get("final", True))}))
            elif kind == "ai":
                await room_manager.broadcast_chat(room_id, envelope("ai", room_id, {"type": "ai", "status": "placeholder", "text": "AI bridge is not connected in this pass."}))
            elif kind == "upload":
                await room_manager.broadcast_chat(room_id, envelope("upload", room_id, {"type": "upload", "status": "placeholder", "metadata": payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}}))
            elif kind == "web_search":
                await room_manager.broadcast_chat(room_id, envelope("debug", room_id, {"type": "web_search", "status": "placeholder"}))
            else:
                await room_manager.broadcast_chat(room_id, envelope("debug", room_id, {"type": kind, "client_id": client_id, "payload": payload}))
    except WebSocketDisconnect:
        await room_manager.unregister(room_id, client_id, "chat")


async def stt_socket(ws: WebSocket) -> None:
    await ws.accept()
    room_id = clean_room(ws.query_params.get("room"))
    cfg = SttConfig()
    await ws.send_json({"type": "status", "status": "server ready", "provider": stt_provider_status()})
    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("text") is not None:
                payload = clean_payload(__import__("json").loads(message["text"]))
                if payload.get("type") == "config":
                    cfg = SttConfig(
                        mime_type=str(payload.get("mime_type") or cfg.mime_type),
                        language_code=str(payload.get("language_code") or cfg.language_code),
                    )
                    await ws.send_json({"type": "status", "status": "server listening", "mime_type": cfg.mime_type, "language_code": cfg.language_code})
                continue
            data = message.get("bytes")
            if not data:
                continue
            try:
                text = await asyncio.to_thread(transcribe_audio_chunk, data, cfg)
            except SttUnavailable as exc:
                await ws.send_json({"type": "error", "error": str(exc)})
                continue
            except Exception as exc:
                await ws.send_json({"type": "error", "error": f"transcribe failed: {type(exc).__name__}"})
                continue
            if text:
                clean = clean_text(text)
                await ws.send_json({"type": "transcript", "text": clean, "final": True, "room": room_id})
    except WebSocketDisconnect:
        return
    finally:
        if ws.client_state != WebSocketState.DISCONNECTED:
            await ws.close()
