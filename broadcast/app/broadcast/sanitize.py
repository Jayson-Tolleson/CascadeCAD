import html
import re
from typing import Any

MAX_ROOM_LEN = 64
MAX_TYPE_LEN = 48
MAX_NAME_LEN = 48
MAX_TEXT_LEN = 2000
_SAFE_TOKEN = re.compile(r"[^a-zA-Z0-9_.:-]+")


def clean_token(value: Any, *, default: str, max_len: int) -> str:
    text = str(value or default).strip()[:max_len]
    text = _SAFE_TOKEN.sub("-", text).strip("-._:")
    return text or default


def clean_room(value: Any) -> str:
    return clean_token(value, default="default", max_len=MAX_ROOM_LEN)


def clean_type(value: Any) -> str:
    return clean_token(value, default="chat", max_len=MAX_TYPE_LEN)


def clean_display_name(value: Any) -> str:
    return html.escape(str(value or "Guest").strip()[:MAX_NAME_LEN], quote=False) or "Guest"


def clean_text(value: Any, *, max_len: int = MAX_TEXT_LEN) -> str:
    return html.escape(str(value or "").replace("\x00", "").strip()[:max_len], quote=False)


def clean_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": "invalid", "error": "message must be a JSON object"}
    data = dict(payload)
    data["type"] = clean_type(data.get("type"))
    if "room" in data:
        data["room"] = clean_room(data.get("room"))
    if "name" in data:
        data["name"] = clean_display_name(data.get("name"))
    if "text" in data:
        data["text"] = clean_text(data.get("text"))
    return data
