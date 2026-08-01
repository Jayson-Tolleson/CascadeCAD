from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .store import atomic_json_write, read_json, validate_id

_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{1,38}[A-Za-z0-9]$")
_ALLOWED_STATUS = {"available", "busy", "invisible"}
_ALLOWED_PROJECT_VISIBILITY = {"hidden", "category", "public"}
_ALLOWED_ROLES = {"owner", "admin", "editor", "reviewer", "viewer"}
_INVITABLE_ROLES = {"admin", "editor", "reviewer", "viewer"}
_ACTIVE_SECONDS = 90
_GLOBAL_SLOW_SECONDS = 8.0
_PROJECT_SLOW_SECONDS = 0.75
_DIRECT_SLOW_SECONDS = 1.0
_GLOBAL_MESSAGE_LIMIT = 500
_PRIVATE_MESSAGE_LIMIT = 2000
_MAX_MESSAGES = 1000
_RETENTION_SECONDS = 30 * 24 * 3600


def _now() -> float:
    return time.time()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _clean_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not text:
        raise ValueError("Message text is required")
    if len(text) > limit:
        raise ValueError(f"Message is limited to {limit} characters")
    return text


def normalize_username(value: Any) -> str:
    username = " ".join(str(value or "").strip().split())
    if not _USERNAME_RE.fullmatch(username):
        raise ValueError("Username must be 3-40 characters using letters, numbers, spaces, ., _, or -")
    return username


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _safe_category(value: Any) -> str:
    category = " ".join(str(value or "").strip().split())[:60]
    return category or "CAD project"


def _message_file_payload(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
        if isinstance(payload.get("messages"), list):
            return payload
    except (OSError, FileNotFoundError, json.JSONDecodeError):
        pass
    return {"version": 1, "messages": []}


class CollaborationStore:
    """Small-server collaboration persistence with UUID identities.

    The first production tier intentionally uses ordinary JSON files so it can
    deploy beside the existing XBF project store. The API boundaries are kept
    database-shaped, allowing PostgreSQL/Redis replacement without changing the
    browser protocol.
    """

    def __init__(self, root: Path):
        self.root = root / "collaboration"
        self.users = self.root / "users"
        self.sessions = self.root / "sessions"
        self.projects = self.root / "projects"
        self.channels = self.root / "channels"
        self.direct = self.root / "direct"
        self.reports = self.root / "reports"
        for directory in (self.users, self.sessions, self.projects, self.channels, self.direct, self.reports):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _user_path(self, user_id: str) -> Path:
        return self.users / f"{validate_id(user_id)}.json"

    def _session_path(self, token: str) -> Path:
        return self.sessions / f"{_token_hash(token)}.json"

    def _project_path(self, project_id: str) -> Path:
        return self.projects / f"{validate_id(project_id)}.json"

    def _channel_path(self, channel: str) -> Path:
        if channel == "global":
            return self.channels / "global.json"
        return self.channels / f"{validate_id(channel)}.json"

    def _direct_path(self, first_user_id: str, second_user_id: str) -> Path:
        pair = sorted((validate_id(first_user_id), validate_id(second_user_id)))
        return self.direct / f"{pair[0]}--{pair[1]}.json"

    def _all_users(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.users.glob("usr_*.json"):
            try:
                rows.append(read_json(path))
            except (OSError, json.JSONDecodeError):
                continue
        return rows

    def _username_owner(self, username: str) -> dict[str, Any] | None:
        folded = username.casefold()
        for user in self._all_users():
            if str(user.get("username", "")).casefold() == folded:
                return user
        return None

    def create_or_resume_session(
        self,
        *,
        username: Any,
        token: str | None = None,
        status: Any = "available",
        project_visibility: Any = "hidden",
        project_category: Any = "CAD project",
    ) -> dict[str, Any]:
        clean_username = normalize_username(username)
        clean_status = str(status or "available").strip().lower()
        clean_visibility = str(project_visibility or "hidden").strip().lower()
        if clean_status not in _ALLOWED_STATUS:
            raise ValueError("Invalid presence status")
        if clean_visibility not in _ALLOWED_PROJECT_VISIBILITY:
            raise ValueError("Invalid project visibility")
        with self._lock:
            if token:
                user = self.authenticate(token)
                owner = self._username_owner(clean_username)
                if owner and owner["id"] != user["id"]:
                    raise ValueError("That username is already in use")
            else:
                owner = self._username_owner(clean_username)
                if owner:
                    raise ValueError("That username already exists on this server; use the original browser session")
                token = secrets.token_urlsafe(36)
                user = {
                    "id": _new_id("usr"),
                    "created_at": _now(),
                    "blocked_user_ids": [],
                }
            user.update({
                "username": clean_username,
                "status": clean_status,
                "project_visibility": clean_visibility,
                "project_category": _safe_category(project_category),
                "updated_at": _now(),
                "last_seen": _now(),
            })
            atomic_json_write(self._user_path(user["id"]), user)
            assert token is not None
            atomic_json_write(self._session_path(token), {
                "version": 1,
                "user_id": user["id"],
                "token_hash": _token_hash(token),
                "created_at": _now(),
                "last_used_at": _now(),
            })
            return {"user": self.public_user(user, requester=user), "session_token": token}

    def authenticate(self, token: str) -> dict[str, Any]:
        token = str(token or "").strip()
        if not token:
            raise PermissionError("A CascadeCAD collaboration session is required")
        try:
            session = read_json(self._session_path(token))
            stored_hash = str(session.get("token_hash", ""))
            if not hmac.compare_digest(stored_hash, _token_hash(token)):
                raise PermissionError("Invalid collaboration session")
            user = read_json(self._user_path(str(session["user_id"])))
        except (OSError, FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as exc:
            raise PermissionError("Invalid or expired collaboration session") from exc
        return user

    def touch_presence(
        self,
        user_id: str,
        *,
        project_id: str | None = None,
        project_name: str | None = None,
        status: Any | None = None,
        project_visibility: Any | None = None,
        project_category: Any | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            user = read_json(self._user_path(user_id))
            if status is not None:
                clean_status = str(status).strip().lower()
                if clean_status not in _ALLOWED_STATUS:
                    raise ValueError("Invalid presence status")
                user["status"] = clean_status
            if project_visibility is not None:
                clean_visibility = str(project_visibility).strip().lower()
                if clean_visibility not in _ALLOWED_PROJECT_VISIBILITY:
                    raise ValueError("Invalid project visibility")
                user["project_visibility"] = clean_visibility
            if project_category is not None:
                user["project_category"] = _safe_category(project_category)
            user["last_seen"] = _now()
            user["updated_at"] = _now()
            if project_id:
                user["active_project_id"] = validate_id(project_id)
                user["active_project_name"] = str(project_name or "CascadeCAD project").strip()[:120]
            atomic_json_write(self._user_path(user_id), user)
            return user

    def public_user(self, user: dict[str, Any], requester: dict[str, Any] | None = None) -> dict[str, Any]:
        visibility = str(user.get("project_visibility", "hidden"))
        project_label = "Private project"
        project_id = None
        if visibility == "category":
            project_label = _safe_category(user.get("project_category"))
        elif visibility == "public":
            project_label = str(user.get("active_project_name") or user.get("project_category") or "Public Showcase")[:120]
            project_id = user.get("active_project_id")
        row = {
            "id": user["id"],
            "username": user.get("username", "CascadeCAD user"),
            "status": user.get("status", "available"),
            "active": _now() - float(user.get("last_seen", 0) or 0) <= _ACTIVE_SECONDS,
            "project_visibility": visibility,
            "project_label": project_label,
            "project_id": project_id,
        }
        if requester and requester.get("id") == user.get("id"):
            row.update({
                "project_category": user.get("project_category", "CAD project"),
                "blocked_user_ids": list(user.get("blocked_user_ids") or []),
            })
        return row

    def active_users(self, requester: dict[str, Any]) -> list[dict[str, Any]]:
        blocked = set(requester.get("blocked_user_ids") or [])
        rows = []
        for user in self._all_users():
            if user.get("id") in blocked or requester.get("id") in set(user.get("blocked_user_ids") or []):
                continue
            if user.get("status") == "invisible" or _now() - float(user.get("last_seen", 0) or 0) > _ACTIVE_SECONDS:
                continue
            rows.append(self.public_user(user, requester=requester))
        return sorted(rows, key=lambda item: (item.get("status") == "busy", str(item.get("username", "")).casefold()))

    def _project_record(self, project_id: str) -> dict[str, Any]:
        path = self._project_path(project_id)
        try:
            return read_json(path)
        except (OSError, FileNotFoundError, json.JSONDecodeError):
            return {"version": 1, "project_id": validate_id(project_id), "members": {}, "created_at": _now()}

    def join_or_claim_project(self, project_id: str, user: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = self._project_record(project_id)
            members = record.setdefault("members", {})
            user_id = user["id"]
            if not members:
                members[user_id] = {"role": "owner", "joined_at": _now(), "invited_by": user_id}
            elif user_id not in members:
                raise PermissionError("This project chat is private. Ask an Owner or Admin to invite your username")
            record["updated_at"] = _now()
            atomic_json_write(self._project_path(project_id), record)
            return {"membership": {"user_id": user_id, **members[user_id]}, "members": self.project_members(project_id, user)}

    def require_member(self, project_id: str, user: dict[str, Any], roles: set[str] | None = None) -> dict[str, Any]:
        record = self._project_record(project_id)
        member = record.get("members", {}).get(user["id"])
        if not member:
            raise PermissionError("You are not a member of this project chat")
        if roles and member.get("role") not in roles:
            raise PermissionError("Your project role does not permit this action")
        return member

    def project_members(self, project_id: str, requester: dict[str, Any]) -> list[dict[str, Any]]:
        self.require_member(project_id, requester)
        record = self._project_record(project_id)
        rows = []
        for user_id, membership in record.get("members", {}).items():
            try:
                user = read_json(self._user_path(user_id))
            except (OSError, FileNotFoundError, json.JSONDecodeError):
                continue
            rows.append({**self.public_user(user, requester=requester), "role": membership.get("role", "viewer")})
        role_order = {"owner": 0, "admin": 1, "editor": 2, "reviewer": 3, "viewer": 4}
        return sorted(rows, key=lambda item: (role_order.get(item.get("role"), 9), str(item.get("username", "")).casefold()))

    def invite_project_user(self, project_id: str, requester: dict[str, Any], username: Any, role: Any) -> dict[str, Any]:
        self.require_member(project_id, requester, {"owner", "admin"})
        clean_username = normalize_username(username)
        clean_role = str(role or "viewer").strip().lower()
        if clean_role not in _INVITABLE_ROLES:
            raise ValueError("Invite role must be Admin, Editor, Reviewer, or Viewer")
        invited = self._username_owner(clean_username)
        if not invited:
            raise ValueError("That username has not created a CascadeCAD user session yet")
        with self._lock:
            record = self._project_record(project_id)
            existing = record.setdefault("members", {}).get(invited["id"])
            if existing and existing.get("role") == "owner":
                raise ValueError("The project Owner role cannot be changed by an invitation")
            record["members"][invited["id"]] = {
                "role": clean_role,
                "joined_at": existing.get("joined_at", _now()) if existing else _now(),
                "invited_by": requester["id"],
            }
            record["updated_at"] = _now()
            atomic_json_write(self._project_path(project_id), record)
        return {"members": self.project_members(project_id, requester)}

    def _rate_limit(self, user: dict[str, Any], key: str, minimum_seconds: float) -> None:
        field = f"last_message_{key}_at"
        last = float(user.get(field, 0) or 0)
        remaining = minimum_seconds - (_now() - last)
        if remaining > 0:
            raise ValueError(f"Slow mode: wait {remaining:.1f} seconds before posting again")
        user[field] = _now()
        atomic_json_write(self._user_path(user["id"]), user)

    def _append_message(self, path: Path, message: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = _message_file_payload(path)
            cutoff = _now() - _RETENTION_SECONDS
            rows = [row for row in payload.get("messages", []) if float(row.get("created_at", 0) or 0) >= cutoff]
            rows.append(message)
            payload["messages"] = rows[-_MAX_MESSAGES:]
            payload["updated_at"] = _now()
            atomic_json_write(path, payload)
        return message

    def _filtered_messages(self, path: Path, requester: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        payload = _message_file_payload(path)
        blocked = set(requester.get("blocked_user_ids") or [])
        rows = [row for row in payload.get("messages", []) if row.get("user_id") not in blocked]
        return rows[-max(1, min(int(limit or 100), 250)):]

    def global_messages(self, requester: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        return self._filtered_messages(self._channel_path("global"), requester, limit)

    def post_global(self, user: dict[str, Any], text: Any) -> dict[str, Any]:
        self._rate_limit(user, "global", _GLOBAL_SLOW_SECONDS)
        message = {
            "id": _new_id("msg"), "channel": "global", "user_id": user["id"],
            "username": user["username"], "text": _clean_text(text, _GLOBAL_MESSAGE_LIMIT),
            "created_at": _now(), "kind": "user",
        }
        return self._append_message(self._channel_path("global"), message)

    def project_messages(self, project_id: str, requester: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        self.require_member(project_id, requester)
        return self._filtered_messages(self._channel_path(project_id), requester, limit)

    def post_project(self, project_id: str, user: dict[str, Any], text: Any, component_ids: Any = None) -> dict[str, Any]:
        self.require_member(project_id, user)
        self._rate_limit(user, "project", _PROJECT_SLOW_SECONDS)
        clean_component_ids = []
        if isinstance(component_ids, list):
            for value in component_ids[:20]:
                value = str(value).strip()
                if value and value not in clean_component_ids:
                    clean_component_ids.append(value[:160])
        message = {
            "id": _new_id("msg"), "channel": project_id, "project_id": project_id,
            "user_id": user["id"], "username": user["username"],
            "text": _clean_text(text, _PRIVATE_MESSAGE_LIMIT), "component_ids": clean_component_ids,
            "created_at": _now(), "kind": "user",
        }
        return self._append_message(self._channel_path(project_id), message)

    def direct_messages(self, requester: dict[str, Any], other_user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        other_user_id = validate_id(other_user_id)
        return self._filtered_messages(self._direct_path(requester["id"], other_user_id), requester, limit)

    def post_direct(self, user: dict[str, Any], other_user_id: str, text: Any) -> dict[str, Any]:
        other_user_id = validate_id(other_user_id)
        if other_user_id == user["id"]:
            raise ValueError("Choose another CascadeCAD user")
        try:
            recipient = read_json(self._user_path(other_user_id))
        except (OSError, FileNotFoundError, json.JSONDecodeError) as exc:
            raise ValueError("Unknown CascadeCAD user") from exc
        if other_user_id in set(user.get("blocked_user_ids") or []) or user["id"] in set(recipient.get("blocked_user_ids") or []):
            raise PermissionError("Direct messages are unavailable for this user")
        self._rate_limit(user, "direct", _DIRECT_SLOW_SECONDS)
        message = {
            "id": _new_id("msg"), "channel": "direct", "user_id": user["id"],
            "recipient_user_id": other_user_id, "username": user["username"],
            "text": _clean_text(text, _PRIVATE_MESSAGE_LIMIT), "created_at": _now(), "kind": "user",
        }
        return self._append_message(self._direct_path(user["id"], other_user_id), message)

    def block_user(self, requester: dict[str, Any], other_user_id: str, blocked: bool) -> dict[str, Any]:
        other_user_id = validate_id(other_user_id)
        if other_user_id == requester["id"]:
            raise ValueError("You cannot block your own account")
        values = set(requester.get("blocked_user_ids") or [])
        if blocked:
            values.add(other_user_id)
        else:
            values.discard(other_user_id)
        requester["blocked_user_ids"] = sorted(values)
        requester["updated_at"] = _now()
        atomic_json_write(self._user_path(requester["id"]), requester)
        return self.public_user(requester, requester=requester)

    def report_message(self, requester: dict[str, Any], message_id: str, reason: Any) -> dict[str, Any]:
        message_id = validate_id(message_id)
        global_messages = _message_file_payload(self._channel_path("global")).get("messages", [])
        if not any(row.get("id") == message_id for row in global_messages):
            raise ValueError("The global-board message no longer exists")
        report = {
            "id": _new_id("rpt"), "message_id": message_id, "reporter_user_id": requester["id"],
            "reason": _clean_text(reason or "Reported from CascadeCAD", 500), "created_at": _now(),
        }
        atomic_json_write(self.reports / f"{report['id']}.json", report)
        return report


class CollaborationHub:
    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(channel)
        if subscribers:
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(channel, None)

    def publish(self, channel: str, event: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers.get(channel, ())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


def register_collaboration_routes(app, project_store, app_path: Callable[[str], str]) -> None:
    from quart import abort, jsonify, request, websocket

    collaboration = CollaborationStore(project_store.root)
    hub = CollaborationHub()
    app.extensions["cascade_cad_collaboration"] = collaboration
    app.extensions["cascade_cad_collaboration_hub"] = hub

    def bearer_token() -> str:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return str(request.args.get("token", "")).strip()

    def current_user() -> dict[str, Any]:
        return collaboration.authenticate(bearer_token())

    def api_error(exc: Exception):
        status = 403 if isinstance(exc, PermissionError) else 400
        return jsonify({"error": str(exc)}), status

    @app.post(app_path("/api/collaboration/session"))
    async def collaboration_session():
        try:
            payload = await request.get_json(force=True)
            result = collaboration.create_or_resume_session(
                username=payload.get("username"), token=payload.get("session_token"),
                status=payload.get("status", "available"),
                project_visibility=payload.get("project_visibility", "hidden"),
                project_category=payload.get("project_category", "CAD project"),
            )
            return jsonify(result)
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/collaboration/presence"))
    async def collaboration_presence():
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            project_id = str(payload.get("project_id") or "").strip() or None
            project_name = None
            if project_id:
                project_name = str(project_store.get_project(project_id).get("name") or "CascadeCAD project")
            updated = collaboration.touch_presence(
                user["id"], project_id=project_id, project_name=project_name,
                status=payload.get("status"), project_visibility=payload.get("project_visibility"),
                project_category=payload.get("project_category"),
            )
            hub.publish("global", {"type": "presence", "user": collaboration.public_user(updated, requester=updated)})
            return jsonify({"user": collaboration.public_user(updated, requester=updated)})
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            return api_error(exc)

    @app.get(app_path("/api/collaboration/users"))
    async def collaboration_users():
        try:
            user = current_user()
            users = collaboration.active_users(user)
            return jsonify({"users": users, "active_count": len(users)})
        except PermissionError as exc:
            return api_error(exc)

    @app.post(app_path("/api/projects/<project_id>/collaboration/join"))
    async def project_collaboration_join(project_id: str):
        try:
            project_store.get_project(project_id)
            user = current_user()
            result = collaboration.join_or_claim_project(project_id, user)
            collaboration.touch_presence(user["id"], project_id=project_id, project_name=project_store.get_project(project_id).get("name"))
            hub.publish(f"project:{project_id}", {"type": "members", "members": result["members"]})
            return jsonify(result)
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            return api_error(exc)

    @app.get(app_path("/api/projects/<project_id>/collaboration/users"))
    async def project_collaboration_users(project_id: str):
        try:
            user = current_user()
            member = collaboration.require_member(project_id, user)
            return jsonify({"membership": {"user_id": user["id"], **member}, "members": collaboration.project_members(project_id, user)})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/projects/<project_id>/collaboration/invite"))
    async def project_collaboration_invite(project_id: str):
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            result = collaboration.invite_project_user(project_id, user, payload.get("username"), payload.get("role"))
            hub.publish(f"project:{project_id}", {"type": "members", "members": result["members"]})
            return jsonify(result)
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.get(app_path("/api/projects/<project_id>/collaboration/messages"))
    async def project_collaboration_messages(project_id: str):
        try:
            user = current_user()
            return jsonify({"messages": collaboration.project_messages(project_id, user, int(request.args.get("limit", 100)))})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/projects/<project_id>/collaboration/messages"))
    async def post_project_collaboration_message(project_id: str):
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            message = collaboration.post_project(project_id, user, payload.get("text"), payload.get("component_ids"))
            hub.publish(f"project:{project_id}", {"type": "message", "message": message})
            return jsonify({"message": message})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.get(app_path("/api/collaboration/global/messages"))
    async def global_collaboration_messages():
        try:
            user = current_user()
            return jsonify({"messages": collaboration.global_messages(user, int(request.args.get("limit", 100)))})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/collaboration/global/messages"))
    async def post_global_collaboration_message():
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            message = collaboration.post_global(user, payload.get("text"))
            hub.publish("global", {"type": "message", "message": message})
            return jsonify({"message": message})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.get(app_path("/api/collaboration/direct/<other_user_id>/messages"))
    async def direct_collaboration_messages(other_user_id: str):
        try:
            user = current_user()
            return jsonify({"messages": collaboration.direct_messages(user, other_user_id, int(request.args.get("limit", 100)))})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/collaboration/direct/<other_user_id>/messages"))
    async def post_direct_collaboration_message(other_user_id: str):
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            message = collaboration.post_direct(user, other_user_id, payload.get("text"))
            channel = "direct:" + ":".join(sorted((user["id"], validate_id(other_user_id))))
            hub.publish(channel, {"type": "message", "message": message})
            return jsonify({"message": message})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/collaboration/users/<other_user_id>/block"))
    async def collaboration_block_user(other_user_id: str):
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            updated = collaboration.block_user(user, other_user_id, bool(payload.get("blocked", True)))
            return jsonify({"user": updated})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    @app.post(app_path("/api/collaboration/messages/<message_id>/report"))
    async def collaboration_report_message(message_id: str):
        try:
            user = current_user()
            payload = await request.get_json(force=True)
            report = collaboration.report_message(user, message_id, payload.get("reason"))
            return jsonify({"ok": True, "report_id": report["id"]})
        except (ValueError, PermissionError) as exc:
            return api_error(exc)

    async def socket_loop(channel: str, user: dict[str, Any]):
        queue = hub.subscribe(channel)
        try:
            await websocket.send_json({"type": "connected", "channel": channel, "user_id": user["id"]})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    event = {"type": "heartbeat", "at": _now()}
                await websocket.send_json(event)
        finally:
            hub.unsubscribe(channel, queue)

    @app.websocket(app_path("/ws/collaboration/global"))
    async def global_collaboration_socket():
        try:
            user = collaboration.authenticate(str(websocket.args.get("token", "")))
            collaboration.touch_presence(user["id"])
        except (ValueError, PermissionError):
            abort(403)
        await socket_loop("global", user)

    @app.websocket(app_path("/ws/projects/<project_id>/collaboration"))
    async def project_collaboration_socket(project_id: str):
        try:
            user = collaboration.authenticate(str(websocket.args.get("token", "")))
            collaboration.require_member(project_id, user)
            project = project_store.get_project(project_id)
            collaboration.touch_presence(user["id"], project_id=project_id, project_name=project.get("name"))
        except (ValueError, PermissionError, FileNotFoundError):
            abort(403)
        await socket_loop(f"project:{project_id}", user)

    @app.websocket(app_path("/ws/collaboration/direct/<other_user_id>"))
    async def direct_collaboration_socket(other_user_id: str):
        try:
            user = collaboration.authenticate(str(websocket.args.get("token", "")))
            other_user_id = validate_id(other_user_id)
        except (ValueError, PermissionError):
            abort(403)
        channel = "direct:" + ":".join(sorted((user["id"], other_user_id)))
        await socket_loop(channel, user)
