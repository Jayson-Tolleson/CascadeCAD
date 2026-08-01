from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from .editor import apply_batch_operation, component_list, migrate_state, new_state, redo, state_summary, undo

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,80}$")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")
ALLOWED_EXTENSIONS = {".xbf", ".step", ".stp", ".fcstd", ".stl", ".obj", ".glb", ".gltf", ".ply", ".3mf"}


def safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", Path(name).name).strip(" ._")
    return cleaned[:180] or "upload.bin"


def validate_id(value: str) -> str:
    if not _ID_RE.fullmatch(value):
        raise ValueError("Invalid identifier")
    return value


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12).replace('-', '_')}"


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.projects = root / "projects"
        self.uploads = root / "uploads"
        self.jobs = root / "jobs"
        self.worker_status_path = root / "worker-status.json"
        for directory in (self.projects, self.uploads, self.jobs):
            directory.mkdir(parents=True, exist_ok=True)

    def set_worker_status(self, **updates: Any) -> dict[str, Any]:
        try:
            status = read_json(self.worker_status_path)
        except (OSError, json.JSONDecodeError, FileNotFoundError):
            status = {}
        status.update(updates)
        status["updated_at"] = time.time()
        atomic_json_write(self.worker_status_path, status)
        return status

    def get_worker_status(self) -> dict[str, Any]:
        try:
            return read_json(self.worker_status_path)
        except (OSError, json.JSONDecodeError, FileNotFoundError):
            return {"state": "unknown", "updated_at": 0}

    def project_dir(self, project_id: str) -> Path:
        return self.projects / validate_id(project_id)

    def project_manifest_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "project.json"

    def editor_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "editor.json"

    def create_project(self, name: str, source_filename: str, import_options: dict[str, Any] | None = None) -> dict[str, Any]:
        project_id = new_id("prj")
        directory = self.project_dir(project_id)
        (directory / "source").mkdir(parents=True)
        (directory / "previews").mkdir()
        (directory / "exports").mkdir()
        (directory / "revisions").mkdir()
        now = time.time()
        manifest = {
            "id": project_id,
            "version": 1,
            "name": (name.strip() or Path(source_filename).stem)[:120],
            "status": "uploading",
            "source_filename": safe_filename(source_filename),
            "source_kind": None,
            "geometry_kind": None,
            "created_at": now,
            "updated_at": now,
            "master_xbf": None,
            "preview_glb": None,
            "step_export": None,
            "step_export_report": None,
            "csg_export": None,
            "csg_export_report": None,
            "brep_export": None,
            "brep_export_report": None,
            "fcstd_export": None,
            "fcstd_export_report": None,
            "xbf_export": None,
            "xbf_export_report": None,
            "exports": {},
            "last_export": None,
            "last_export_format": None,
            "last_export_report": None,
            "components": [],
            "combined_projects": [],
            "import_options": dict(import_options or {}),
            "mesh_cleanup": None,
            "message": "Waiting for upload",
        }
        atomic_json_write(self.project_manifest_path(project_id), manifest)
        return manifest

    def update_project(self, project_id: str, **updates: Any) -> dict[str, Any]:
        path = self.project_manifest_path(project_id)
        manifest = read_json(path)
        manifest.update(updates)
        manifest["updated_at"] = time.time()
        atomic_json_write(path, manifest)
        return manifest

    def get_project(self, project_id: str) -> dict[str, Any]:
        return read_json(self.project_manifest_path(project_id))

    def reset_editor(self, project_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
        state = new_state(components)
        atomic_json_write(self.editor_path(project_id), state)
        return state

    def get_editor(self, project_id: str) -> dict[str, Any]:
        path = self.editor_path(project_id)
        if path.exists():
            state = migrate_state(read_json(path))
            # Persist one-time migrations so future requests stay inexpensive.
            atomic_json_write(path, state)
            return state
        manifest = self.get_project(project_id)
        return self.reset_editor(project_id, manifest.get("components", []))

    def save_editor(self, project_id: str, state: dict[str, Any]) -> dict[str, Any]:
        atomic_json_write(self.editor_path(project_id), state)
        return state

    def apply_editor_operation(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        state = apply_batch_operation(self.get_editor(project_id), payload)
        self.save_editor(project_id, state)
        return {"editor": state_summary(state), "components": component_list(state)}

    def undo_editor(self, project_id: str) -> dict[str, Any]:
        state = undo(self.get_editor(project_id))
        self.save_editor(project_id, state)
        return {"editor": state_summary(state), "components": component_list(state)}

    def redo_editor(self, project_id: str) -> dict[str, Any]:
        state = redo(self.get_editor(project_id))
        self.save_editor(project_id, state)
        return {"editor": state_summary(state), "components": component_list(state)}

    def get_project_view(self, project_id: str) -> dict[str, Any]:
        manifest = self.get_project(project_id)
        state = self.get_editor(project_id)
        manifest["components"] = component_list(state)
        manifest["editor"] = state_summary(state)
        return manifest

    def list_projects(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.projects.glob("prj_*/project.json"):
            try:
                rows.append(read_json(path))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(rows, key=lambda item: item.get("updated_at", 0), reverse=True)

    def delete_project(self, project_id: str) -> None:
        project_id = validate_id(project_id)
        manifest = self.get_project(project_id)
        if manifest.get("status") in {"uploading", "queued", "processing"}:
            raise ValueError("Wait for the active upload or geometry job before deleting this project")
        for job_path in self.jobs.glob("job_*.json"):
            try:
                job = read_json(job_path)
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") not in {"queued", "running"}:
                continue
            source_ids = job.get("payload", {}).get("source_project_ids") or []
            if job.get("project_id") == project_id or project_id in source_ids:
                raise ValueError("This project is being used by an active geometry job")
        shutil.rmtree(self.project_dir(project_id))

        # Clean up completed/failed job records and abandoned upload metadata
        # belonging to the deleted project. Active projects are rejected above.
        for job_path in self.jobs.glob("job_*.json"):
            try:
                job = read_json(job_path)
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("project_id") == project_id:
                job_path.unlink(missing_ok=True)
        for upload_path in self.uploads.glob("upl_*"):
            try:
                upload = read_json(upload_path / "upload.json")
            except (OSError, json.JSONDecodeError, FileNotFoundError):
                continue
            if upload.get("project_id") == project_id:
                shutil.rmtree(upload_path, ignore_errors=True)

    def create_upload(self, project_id: str, filename: str, size: int, options: dict[str, Any] | None = None) -> dict[str, Any]:
        upload_id = new_id("upl")
        upload_dir = self.uploads / upload_id
        upload_dir.mkdir()
        clean_name = safe_filename(filename)
        metadata = {
            "id": upload_id,
            "project_id": validate_id(project_id),
            "filename": clean_name,
            "size": size,
            "received": 0,
            "created_at": time.time(),
            "complete": False,
            "options": dict(options or {}),
        }
        atomic_json_write(upload_dir / "upload.json", metadata)
        (upload_dir / "payload.part").touch()
        return metadata

    def upload_dir(self, upload_id: str) -> Path:
        return self.uploads / validate_id(upload_id)

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        return read_json(self.upload_dir(upload_id) / "upload.json")

    def append_chunk(self, upload_id: str, offset: int, data: bytes) -> dict[str, Any]:
        upload_dir = self.upload_dir(upload_id)
        metadata_path = upload_dir / "upload.json"
        metadata = read_json(metadata_path)
        payload_path = upload_dir / "payload.part"
        current = payload_path.stat().st_size

        # Make chunk PUT requests idempotent. A proxy may deliver a chunk to the
        # server and then lose the response, causing the browser to resend the
        # same offset. Verify the existing bytes and return success instead of
        # breaking the upload with an offset mismatch.
        if offset < current:
            end = offset + len(data)
            if end > current:
                raise ValueError(f"Offset mismatch: server has {current} bytes")
            with payload_path.open("rb") as handle:
                handle.seek(offset)
                existing = handle.read(len(data))
            if existing != data:
                raise ValueError(f"Chunk conflict at offset {offset}")
            metadata["received"] = current
            atomic_json_write(metadata_path, metadata)
            return metadata

        if offset != current or offset != metadata["received"]:
            raise ValueError(f"Offset mismatch: server has {current} bytes")
        if current + len(data) > metadata["size"]:
            raise ValueError("Chunk exceeds declared upload size")
        free_bytes = shutil.disk_usage(self.root).free
        if free_bytes < len(data) + 256 * 1024**2:
            raise ValueError(
                "Server storage is nearly full. Clean old projects before continuing the upload."
            )
        with payload_path.open("ab", buffering=0) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        metadata["received"] = current + len(data)
        atomic_json_write(metadata_path, metadata)
        return metadata

    def finish_upload(self, upload_id: str) -> tuple[dict[str, Any], Path]:
        upload_dir = self.upload_dir(upload_id)
        metadata_path = upload_dir / "upload.json"
        metadata = read_json(metadata_path)
        payload_path = upload_dir / "payload.part"
        project_id = metadata["project_id"]
        target = self.project_dir(project_id) / "source" / metadata["filename"]

        # Finish is also idempotent: a lost HTTP response must not force the
        # user to upload a multi-gigabyte model again.
        if metadata.get("complete"):
            if not target.exists():
                raise FileNotFoundError("Completed upload payload is missing")
            return metadata, target

        actual = payload_path.stat().st_size
        if actual != metadata["size"]:
            raise ValueError(f"Upload incomplete: received {actual} of {metadata['size']} bytes")
        os.replace(payload_path, target)
        metadata["complete"] = True
        metadata["received"] = actual
        metadata["completed_at"] = time.time()
        atomic_json_write(metadata_path, metadata)
        return metadata, target

    def create_job(self, operation: str, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = new_id("job")
        job = {
            "id": job_id,
            "operation": operation,
            "project_id": validate_id(project_id),
            "payload": payload,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "error": None,
            "attempts": 0,
        }
        atomic_json_write(self.jobs / f"{job_id}.json", job)
        return job

    def get_job(self, job_id: str) -> dict[str, Any]:
        return read_json(self.jobs / f"{validate_id(job_id)}.json")

    def update_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        path = self.jobs / f"{validate_id(job_id)}.json"
        job = read_json(path)
        job.update(updates)
        job["updated_at"] = time.time()
        atomic_json_write(path, job)
        return job


    def request_job_cancel(self, job_id: str) -> dict[str, Any]:
        path = self.jobs / f"{validate_id(job_id)}.json"
        job = read_json(path)
        status = str(job.get("status", ""))
        if status in {"complete", "failed", "cancelled"}:
            return job
        now = time.time()
        if status == "queued":
            job.update(
                status="cancelled",
                cancel_requested=True,
                progress=int(job.get("progress", 0) or 0),
                message="Cancelled before processing",
                error=None,
                updated_at=now,
                finished_at=now,
            )
            try:
                self.update_project(
                    str(job.get("project_id", "")),
                    status="ready",
                    message="Queued job cancelled",
                )
            except (ValueError, FileNotFoundError):
                pass
        else:
            job.update(
                cancel_requested=True,
                message="Cancellation requested; finishing the current geometry chunk",
                updated_at=now,
            )
        atomic_json_write(path, job)
        return job

    def job_cancel_requested(self, job_id: str) -> bool:
        try:
            return bool(self.get_job(job_id).get("cancel_requested", False))
        except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError):
            return False

    def recover_interrupted_jobs(self, recovery_limit: int = 1) -> dict[str, int]:
        """Recover jobs left running when the single worker process exited.

        A system OOM kill cannot execute Python exception handling, so jobs can
        otherwise remain permanently marked running. The service has only one
        worker instance; therefore every running record found at startup is an
        orphan from the previous process.
        """
        recovered = 0
        failed = 0
        for path in self.jobs.glob("job_*.json"):
            try:
                job = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") != "running":
                continue
            if job.get("cancel_requested"):
                job.update(
                    status="cancelled",
                    message="Cancelled after worker restart",
                    error=None,
                    finished_at=time.time(),
                    updated_at=time.time(),
                )
                atomic_json_write(path, job)
                try:
                    self.update_project(str(job.get("project_id", "")), status="ready", message="Export cancelled")
                except (ValueError, FileNotFoundError):
                    pass
                continue
            attempts = int(job.get("attempts", 0)) + 1
            project_id = str(job.get("project_id", ""))
            if attempts <= recovery_limit:
                job.update(
                    status="queued",
                    attempts=attempts,
                    progress=0,
                    message=f"Recovered after worker restart (attempt {attempts})",
                    error=None,
                    updated_at=time.time(),
                )
                atomic_json_write(path, job)
                try:
                    self.update_project(
                        project_id,
                        status="queued",
                        message="Geometry worker restarted; job will resume",
                    )
                except (ValueError, FileNotFoundError):
                    pass
                recovered += 1
            else:
                message = (
                    "Geometry worker was interrupted repeatedly, usually by memory pressure. "
                    "The server remains online; use a smaller part or a larger conversion machine."
                )
                job.update(
                    status="failed",
                    attempts=attempts,
                    message=message,
                    error=message,
                    updated_at=time.time(),
                )
                atomic_json_write(path, job)
                try:
                    self.update_project(project_id, status="failed", message=message)
                except (ValueError, FileNotFoundError):
                    pass
                failed += 1
        return {"recovered": recovered, "failed": failed}

    def queued_jobs(self) -> list[dict[str, Any]]:
        rows = []
        for path in self.jobs.glob("job_*.json"):
            try:
                job = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") == "queued":
                rows.append(job)
        return sorted(rows, key=lambda item: item.get("created_at", 0))
