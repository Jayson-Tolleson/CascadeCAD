from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from uuid import uuid4

from quart import Quart, abort, jsonify, redirect, render_template, request, send_file, websocket

from .config import Settings

def unit_options():
    return [{"label": "Imperial (inches / pounds)", "value": "imperial"}, {"label": "Metric (millimeters / kilograms)", "value": "metric"}]

from .store import ALLOWED_EXTENSIONS, Store, safe_filename
from .share_media import cleanup_share_media, normalize_share_image, normalize_share_video
from .collaboration import register_collaboration_routes


def _payload_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> Quart:
    settings = Settings.from_env()

    def app_path(path: str) -> str:
        if path == "/":
            return f"{settings.base_path}/" if settings.base_path else "/"
        return f"{settings.base_path}{path}"

    app = Quart(__name__, static_url_path=app_path("/static"))
    app.secret_key = settings.secret_key
    app.config["MAX_CONTENT_LENGTH"] = max(settings.chunk_bytes + 1024 * 1024, 19 * 1024 * 1024)
    app.config["APPLICATION_ROOT"] = settings.base_path or "/"
    store = Store(settings.storage)
    app.extensions["cascade_cad_settings"] = settings

    @app.after_request
    async def prevent_stale_frontend_modules(response):
        # ES-module dependency URLs are aggressively cached by browsers. During
        # in-place upgrades, stale nested imports can make Firefox report only
        # that project.js failed. Keep JS modules revalidated until filenames
        # become content-hashed in a later release.
        if request.path.startswith(app_path("/static/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    app.extensions["cascade_cad_store"] = store
    register_collaboration_routes(app, store, app_path)

    if settings.base_path:
        @app.get("/")
        async def service_root():
            return redirect(app_path("/"), code=308)

        @app.get(settings.base_path)
        async def base_redirect():
            return redirect(app_path("/"), code=308)

    @app.get(app_path("/"))
    async def index():
        projects = store.list_projects()
        if projects:
            project_id = projects[0]["id"]
        else:
            manifest = store.create_project("Untitled", "untitled.step")
            project_id = manifest["id"]
        manifest = store.get_project_view(project_id)
        return await render_template(
            "project.html",
            project=manifest,
            base_path=settings.base_path,
        )
    @app.get(app_path("/project/<project_id>"))
    async def project_page(project_id: str):
        try:
            manifest = store.get_project_view(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        return await render_template(
            "project.html",
            project=manifest,
            base_path=settings.base_path,
        )

    @app.get(app_path("/healthz"))
    async def healthz():
        worker = store.get_worker_status()
        worker_age = max(0.0, time.time() - float(worker.get("updated_at", 0) or 0))
        disk = shutil.disk_usage(settings.storage)
        smoke_status_path = settings.storage / "diagnostics" / "step-export-smoke.status"
        try:
            step_smoke_status = smoke_status_path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            step_smoke_status = "not-run"
        export_smoke_path = settings.storage / "diagnostics" / "export-suite-smoke.status"
        try:
            export_smoke_status = export_smoke_path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            export_smoke_status = "not-run"
        hard_speed_smoke_path = settings.storage / "diagnostics" / "hard-speed-smoke.status"
        try:
            hard_speed_smoke_status = hard_speed_smoke_path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            hard_speed_smoke_status = "not-run"
        return jsonify(
            {
                "ok": True,
                "service": "cascade-cad",
                "version": "1.0.0",
                "base_path": settings.base_path,
                "editor": True,
                "frontend_dependency_fix": True,
                "multi_project_editor": True,
                "project_delete": True,
                "resilient_jobs": True,
                "mesh_cleanup": True,
                "solid_toolbars": True,
                "advanced_solid_operations": [
                    "cone", "extrude", "revolve", "cross_section", "sweep", "loft",
                    "fillet", "chamfer", "additive_helix", "subtractive_helix",
                ],
                "draft_toolbar": ["line", "bspline", "polyline", "circle", "rectangle", "polygon", "ellipse"],
                "mesh_to_solids_assembly_workflow": True,
                "step_ap242_export": True,
                "selected_step_export": True,
                "faceted_step_fallback": True,
                "step_export_smoke": step_smoke_status,
                "export_suite_smoke": export_smoke_status,
                "editor_themes": ["light", "dark", "system"],
                "engineering_units": unit_options(),
                "triangle_budgets": [5_000_000, 10_000_000, 25_000_000, 50_000_000],
                "rendering": {
                    "default_triangle_budget": 25_000_000,
                    "progressive_mesh_loading": True,
                    "frustum_culling": True,
                    "lazy_loading": True,
                    "gpu_instancing_ready": True,
                    "diagnostics_overlay": True,
                },
                "export_formats": ["xbf", "step", "csg", "brep", "fcstd"],
                "automatic_downloads": True,
                "cancellable_exports": True,
                "responsive_toolbar": True,
                "validated_brep_export": True,
                "part_based_fcstd_export": True,
                "faceted_xbf_conversion": True,
                "hard_speed_faceted_conversion": True,
                "hard_speed_smoke": hard_speed_smoke_status,
                "fast_sewing": True,
                "csg_separate_parts": True,
                "square_capture_share": True,
                "share_recording_max_seconds": 60,
                "share_media_formats": ["image/jpeg", "video/mp4"],
                "collaboration": {
                    "uuid_users": True,
                    "project_chat": True,
                    "direct_messages": True,
                    "global_presence": True,
                    "global_broadcast_board": True,
                    "privacy_modes": ["hidden", "category", "public"],
                    "presence_modes": ["available", "busy", "invisible"],
                    "project_roles": ["owner", "admin", "editor", "reviewer", "viewer"],
                },
                "social_share_targets": ["bluesky", "instagram"],
                "worker": {
                    **worker,
                    "age_seconds": round(worker_age, 1),
                    "responsive": worker_age < 30,
                },
                "storage": {
                    "total_bytes": disk.total,
                    "used_bytes": disk.used,
                    "free_bytes": disk.free,
                },
            }
        )

    @app.get(app_path("/api/projects"))
    async def list_projects():
        return jsonify({"projects": store.list_projects()})

    @app.get(app_path("/api/projects/<project_id>"))
    async def get_project(project_id: str):
        try:
            return jsonify(store.get_project_view(project_id))
        except (ValueError, FileNotFoundError):
            abort(404)

    @app.delete(app_path("/api/projects/<project_id>"))
    async def delete_project(project_id: str):
        try:
            store.delete_project(project_id)
        except FileNotFoundError:
            abort(404)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify({"ok": True})

    @app.post(app_path("/api/uploads/start"))
    async def start_upload():
        payload = await request.get_json(force=True)
        filename = safe_filename(str(payload.get("filename", "")))
        size = int(payload.get("size", 0))
        name = str(payload.get("project_name", "")).strip()
        suffix = Path(filename).suffix.lower()
        if suffix not in ['.step', '.stp', '.iges', '.igs', '.brep', '.stl', '.obj', '.gltf', '.glb', '.fcstd', '.xbf', 'step', 'stp', 'iges', 'igs', 'brep', 'stl', 'obj', 'gltf', 'glb', 'fcstd', 'xbf']:
            return jsonify({"error": f"Unsupported file type: {suffix}"}), 400
        if size <= 0 or size > settings.max_upload_bytes:
            return jsonify({"error": "File size is outside the configured limit"}), 400
        requested_cleanup = bool(payload.get("mesh_cleanup", False)) and suffix in {".stl", ".obj", ".glb", ".gltf", ".ply", ".3mf"}
        free_bytes = shutil.disk_usage(settings.storage).free
        # 3MF cleanup temporarily stores expanded XML before Trimesh imports it.
        multiplier = 5 if requested_cleanup and suffix == ".3mf" else 3 if requested_cleanup else 2
        estimated_required = (size * multiplier) + settings.storage_reserve_bytes
        if free_bytes < estimated_required:
            return jsonify(
                {
                    "error": (
                        f"Insufficient server storage. This upload and its XBF/preview need approximately "
                        f"{estimated_required} bytes, but only {free_bytes} bytes are free. "
                        "Delete old projects or run cascade-cad-maintenance."
                    )
                }
            ), 507
        mesh_cleanup = requested_cleanup
        options = {"mesh_cleanup": mesh_cleanup}
        project = store.create_project(name, filename, import_options=options)
        upload = store.create_upload(project["id"], filename, size, options=options)
        return jsonify({"project": project, "upload": upload, "chunk_bytes": settings.chunk_bytes})

    @app.get(app_path("/api/uploads/<upload_id>"))
    async def get_upload(upload_id: str):
        try:
            return jsonify(store.get_upload(upload_id))
        except (ValueError, FileNotFoundError):
            abort(404)

    @app.put(app_path("/api/uploads/<upload_id>/chunk"))
    async def upload_chunk(upload_id: str):
        try:
            offset = int(request.args.get("offset", "-1"))
            data = await request.get_data()
            if not data:
                return jsonify({"error": "Empty chunk"}), 400
            return jsonify(store.append_chunk(upload_id, offset, data))
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 409

    @app.post(app_path("/api/uploads/<upload_id>/finish"))
    async def finish_upload(upload_id: str):
        try:
            metadata, source = store.finish_upload(upload_id)
            project_id = metadata["project_id"]
            options = dict(metadata.get("options") or {})
            cleanup = bool(options.get("mesh_cleanup", False))
            message = "Queued for mesh cleanup and geometry import" if cleanup else "Queued for geometry import"
            store.update_project(project_id, status="queued", message=message, import_options=options)
            job = store.create_job("import", project_id, {"source": str(source), **options})
            return jsonify({"project_id": project_id, "job": job})
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get(app_path("/api/jobs/<job_id>"))
    async def get_job(job_id: str):
        try:
            return jsonify(store.get_job(job_id))
        except (ValueError, FileNotFoundError):
            abort(404)

    @app.post(app_path("/api/jobs/<job_id>/cancel"))
    async def cancel_job(job_id: str):
        try:
            job = store.request_job_cancel(job_id)
            return jsonify({"job": job})
        except (ValueError, FileNotFoundError):
            abort(404)

    @app.websocket(app_path("/ws/jobs/<job_id>"))
    async def job_socket(job_id: str):
        last = None
        while True:
            try:
                job = store.get_job(job_id)
            except (ValueError, FileNotFoundError):
                await websocket.send_json({"status": "missing"})
                return
            marker = (job.get("status"), job.get("progress"), job.get("message"))
            if marker != last:
                await websocket.send_json(job)
                last = marker
            if job.get("status") in {"complete", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.75)

    @app.post(app_path("/api/projects/<project_id>/editor"))
    async def editor_operation(project_id: str):
        try:
            manifest = store.get_project(project_id)
            if manifest.get("status") in {"queued", "processing", "uploading"}:
                return jsonify({"error": "A geometry job is already running"}), 409
            payload = await request.get_json(force=True)
            return jsonify(store.apply_editor_operation(project_id, payload))
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post(app_path("/api/projects/<project_id>/editor/undo"))
    async def editor_undo(project_id: str):
        try:
            return jsonify(store.undo_editor(project_id))
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 409

    @app.post(app_path("/api/projects/<project_id>/editor/redo"))
    async def editor_redo(project_id: str):
        try:
            return jsonify(store.redo_editor(project_id))
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 409

    @app.post(app_path("/api/projects/<project_id>/editor/commit"))
    async def editor_commit(project_id: str):
        try:
            manifest = store.get_project(project_id)
            if manifest.get("status") in {"queued", "processing", "uploading"}:
                return jsonify({"error": "A geometry job is already running"}), 409
            state = store.get_editor(project_id)
            if state.get("revision") == state.get("saved_revision"):
                return jsonify({"error": "There are no uncommitted editor changes"}), 409
            job = store.create_job("commit_edits", project_id, {"editor_revision": state.get("revision")})
            store.update_project(project_id, status="queued", message="Committing editor changes to XBF")
            return jsonify({"job": job})
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post(app_path("/api/projects/<project_id>/combine"))
    async def combine_project_assemblies(project_id: str):
        try:
            target = store.get_project(project_id)
            if target.get("status") in {"queued", "processing", "uploading"}:
                return jsonify({"error": "A geometry job is already running"}), 409
            payload = await request.get_json(force=True)
            raw_ids = payload.get("source_project_ids") or []
            if not isinstance(raw_ids, list):
                raise ValueError("source_project_ids must be a list")
            source_ids = []
            for value in raw_ids:
                source_id = str(value).strip()
                if source_id == project_id or source_id in source_ids:
                    continue
                source = store.get_project(source_id)
                if source.get("status") != "ready" or not source.get("master_xbf"):
                    raise ValueError(f"Project is not ready to combine: {source.get('name', source_id)}")
                source_ids.append(source_id)
            if not source_ids:
                raise ValueError("Select at least one other ready project")
            if len(source_ids) > 20:
                raise ValueError("Combine no more than 20 projects in one operation")
            job = store.create_job("combine_projects", project_id, {"source_project_ids": source_ids})
            store.update_project(
                project_id,
                status="queued",
                message=f"Queued combination of {len(source_ids)} project{'s' if len(source_ids) != 1 else ''}",
            )
            return jsonify({"job": job})
        except FileNotFoundError:
            abort(404)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post(app_path("/api/projects/<project_id>/editor/split"))
    async def editor_split(project_id: str):
        try:
            manifest = store.get_project(project_id)
            if manifest.get("geometry_kind") in {"mesh", "mixed"}:
                return jsonify({"error": "Mesh components must be reconstructed before exact solid splitting"}), 409
            payload = await request.get_json(force=True)
            component_id = str(payload.get("component_id", "")).strip()
            if not component_id:
                raise ValueError("component_id is required")
            job = store.create_job("split_component", project_id, {"component_id": component_id})
            store.update_project(project_id, status="queued", message="Splitting selected component")
            return jsonify({"job": job})
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400


    @app.post(app_path("/api/projects/<project_id>/model"))
    async def model_operation(project_id: str):
        try:
            manifest = store.get_project(project_id)
            if manifest.get("status") in {"queued", "processing", "uploading"}:
                return jsonify({"error": "A geometry job is already running"}), 409
            payload = await request.get_json(force=True)
            operation = str(payload.get("operation", "")).strip().lower()
            allowed = {
                "box", "cylinder", "pipe", "sphere", "torus", "cone",
                "line", "bspline", "polyline", "circle", "rectangle", "polygon", "ellipse",
                "extrude", "revolve", "cross_section", "sweep", "loft",
                "fuse", "subtract", "mirror", "facebinder",
                "fillet", "chamfer", "additive_helix", "subtractive_helix",
            }
            if operation not in allowed:
                raise ValueError(f"Unsupported modeling operation: {operation}")
            exact_selection_operations = {
                "fuse", "subtract", "mirror", "facebinder",
                "extrude", "revolve", "cross_section", "sweep", "loft",
                "fillet", "chamfer", "additive_helix", "subtractive_helix",
            }
            if manifest.get("geometry_kind") in {"mesh", "mixed"} and operation in exact_selection_operations:
                return jsonify({"error": "This operation requires exact or faceted B-rep components. Use Convert to Tessellated (Faceted) Solids first for mesh-derived assembly parts."}), 409
            component_ids = payload.get("component_ids") or []
            if not isinstance(component_ids, list):
                raise ValueError("component_ids must be a list")
            job_payload = {
                "operation": operation,
                "parameters": payload.get("parameters") or {},
                "component_ids": [str(value) for value in component_ids if str(value).strip()],
            }
            job = store.create_job("model_operation", project_id, job_payload)
            store.update_project(project_id, status="queued", message=f"Queued {operation} operation")
            return jsonify({"job": job})
        except FileNotFoundError:
            abort(404)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400


    @app.post(app_path("/api/projects/<project_id>/inspect"))
    async def inspect_project_components(project_id: str):
        try:
            manifest = store.get_project(project_id)
            if not manifest.get("master_xbf"):
                return jsonify({"error": "Project master.xbf is not ready"}), 409
            payload = await request.get_json(silent=True) or {}
            component_ids = payload.get("component_ids") or []
            if not isinstance(component_ids, list):
                raise ValueError("component_ids must be a list")
            component_ids = [str(value) for value in component_ids if str(value).strip()]
            if not component_ids:
                raise ValueError("Select at least one part")
            from .geometry import inspect_components
            result = await asyncio.to_thread(
                inspect_components,
                store.project_dir(project_id),
                store.get_editor(project_id),
                component_ids,
            )
            return jsonify(result)
        except FileNotFoundError:
            abort(404)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post(app_path("/api/projects/<project_id>/convert/faceted-solids"))
    async def convert_project_to_faceted_solids(project_id: str):
        try:
            manifest = store.get_project(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        if manifest.get("status") in {"queued", "processing", "uploading"}:
            return jsonify({"error": "A geometry job is already running"}), 409
        if not manifest.get("master_xbf"):
            return jsonify({"error": "Project master.xbf is not ready"}), 409
        payload = await request.get_json(silent=True) or {}
        fast_render = _payload_bool(payload.get("fast_render", False))
        job = store.create_job("convert_faceted_solids", project_id, {"fast_render": fast_render})
        store.update_project(
            project_id,
            status="queued",
            message=(
                "Queued hard-speed faceted conversion with FastSewing"
                if fast_render
                else "Queued hard-speed conversion of XBF mesh remnants to faceted BREP solids"
            ),
        )
        return jsonify({"job": job})

    @app.post(app_path("/api/projects/<project_id>/export"))
    async def request_export(project_id: str):
        try:
            manifest = store.get_project(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        if manifest.get("status") in {"queued", "processing", "uploading"}:
            return jsonify({"error": "A geometry job is already running"}), 409
        payload = await request.get_json(silent=True) or {}
        export_format = str(payload.get("format", "")).lower().lstrip(".")
        if export_format not in {"xbf", "step", "csg", "brep", "fcstd"}:
            return jsonify({"error": "format must be xbf, step, csg, brep, or fcstd"}), 400
        component_ids = payload.get("component_ids") or []
        if not isinstance(component_ids, list):
            return jsonify({"error": "component_ids must be a list"}), 400
        component_ids = [str(value) for value in component_ids if str(value).strip()]
        fast_render = _payload_bool(payload.get("fast_render", False))
        unit_system = str(payload.get("unit_system", "imperial")).strip().lower()
        if unit_system not in {"imperial", "metric"}:
            return jsonify({"error": "unit_system must be imperial or metric"}), 400
        job = store.create_job(
            "export_file",
            project_id,
            {
                "format": export_format,
                "component_ids": component_ids,
                "fast_render": fast_render,
                "unit_system": unit_system,
            },
        )
        scope = "selected components" if component_ids else "complete project"
        store.update_project(
            project_id,
            status="queued",
            message=f"{export_format.upper()} export queued for {scope}",
        )
        return jsonify({"job": job, "scope": scope, "format": export_format})

    @app.post(app_path("/api/projects/<project_id>/export/step"))
    async def request_step_export_compat(project_id: str):
        payload = await request.get_json(silent=True) or {}
        payload["format"] = "step"
        try:
            manifest = store.get_project(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        if manifest.get("status") in {"queued", "processing", "uploading"}:
            return jsonify({"error": "A geometry job is already running"}), 409
        component_ids = payload.get("component_ids") or []
        if not isinstance(component_ids, list):
            return jsonify({"error": "component_ids must be a list"}), 400
        component_ids = [str(value) for value in component_ids if str(value).strip()]
        job = store.create_job(
            "export_file",
            project_id,
            {
                "format": "step",
                "component_ids": component_ids,
                "fast_render": _payload_bool(payload.get("fast_render", False)),
                "unit_system": str(payload.get("unit_system", "imperial")).strip().lower(),
            },
        )
        store.update_project(project_id, status="queued", message="STEP export queued")
        return jsonify({"job": job, "format": "step"})

    @app.post(app_path("/api/projects/<project_id>/share-media/normalize"))
    async def normalize_share_media(project_id: str):
        try:
            store.get_project(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        if request.content_length and request.content_length > 18 * 1024 * 1024:
            return jsonify({"error": "Capture exceeds the 18 MiB social-media preparation limit"}), 413
        files = await request.files
        form = await request.form
        upload = files.get("media")
        kind = str(form.get("kind", "")).strip().lower()
        if upload is None or kind not in {"image", "video"}:
            return jsonify({"error": "media file and kind=image|video are required"}), 400

        share_dir = store.project_dir(project_id) / "share-media"
        share_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(cleanup_share_media, share_dir)
        capture_id = uuid4().hex
        source_suffix = Path(upload.filename or "capture.bin").suffix.lower() or ".bin"
        source_path = share_dir / f".{capture_id}-source{source_suffix}"
        destination: Path | None = None
        try:
            await asyncio.to_thread(upload.save, source_path)
            if not source_path.exists() or source_path.stat().st_size == 0:
                raise ValueError("The uploaded capture was empty")
            if source_path.stat().st_size > 18 * 1024 * 1024:
                raise ValueError("Capture exceeds the 18 MiB social-media preparation limit")

            project_name = safe_filename(str(store.get_project(project_id).get("name") or "cascade-cad"))
            if kind == "image":
                destination = share_dir / f"{capture_id}.jpg"
                try:
                    await asyncio.to_thread(normalize_share_image, source_path, destination)
                except OSError as exc:
                    raise ValueError(f"Unsupported or damaged image capture: {exc}") from exc
                mime_type = "image/jpeg"
                extension = "jpg"
            else:
                destination = share_dir / f"{capture_id}.mp4"
                await normalize_share_video(source_path, destination)
                mime_type = "video/mp4"
                extension = "mp4"
        except (ValueError, RuntimeError) as exc:
            if destination is not None:
                destination.unlink(missing_ok=True)
            return jsonify({"error": str(exc)}), 400
        finally:
            source_path.unlink(missing_ok=True)

        assert destination is not None
        download_name = f"{Path(project_name).stem or 'cascade-cad'}-{capture_id[:8]}.{extension}"
        return jsonify({
            "ok": True,
            "kind": kind,
            "filename": download_name,
            "mime_type": mime_type,
            "size_bytes": destination.stat().st_size,
            "url": app_path(f"/api/projects/{project_id}/share-media/{destination.name}"),
            "expires_in_seconds": 24 * 3600,
        })

    @app.get(app_path("/api/projects/<project_id>/share-media/<filename>"))
    async def get_share_media(project_id: str, filename: str):
        try:
            store.get_project(project_id)
        except (ValueError, FileNotFoundError):
            abort(404)
        if Path(filename).name != filename or not filename.endswith((".jpg", ".mp4")):
            abort(404)
        path = store.project_dir(project_id) / "share-media" / filename
        if not path.is_file():
            abort(404)
        return await send_file(
            path,
            mimetype="image/jpeg" if filename.endswith(".jpg") else "video/mp4",
            conditional=True,
        )

    @app.get(app_path("/api/projects/<project_id>/preview"))
    async def preview(project_id: str):
        try:
            manifest = store.get_project(project_id)
            relative = manifest.get("preview_glb")
            if not relative:
                abort(404)
            return await send_file(
                store.project_dir(project_id) / relative,
                mimetype="model/gltf-binary",
                conditional=True,
            )
        except (ValueError, FileNotFoundError):
            abort(404)

    @app.get(app_path("/api/projects/<project_id>/download/<kind>"))
    async def download(project_id: str, kind: str):
        try:
            manifest = store.get_project(project_id)
            exports = dict(manifest.get("exports") or {})
            mapping = {
                "xbf": (exports.get("xbf") or {}).get("relative_path") or manifest.get("xbf_export") or manifest.get("master_xbf"),
                "step": (exports.get("step") or {}).get("relative_path") or manifest.get("step_export"),
                "csg": (exports.get("csg") or {}).get("relative_path") or manifest.get("csg_export"),
                "brep": (exports.get("brep") or {}).get("relative_path") or manifest.get("brep_export"),
                "fcstd": (exports.get("fcstd") or {}).get("relative_path") or manifest.get("fcstd_export"),
                "glb": manifest.get("preview_glb"),
            }
            relative = mapping.get(kind.lower())
            if not relative:
                abort(404)
            mimetypes = {
                "step": "model/step",
                "csg": "text/plain; charset=utf-8",
                "brep": "application/octet-stream",
                "fcstd": "application/zip",
                "glb": "model/gltf-binary",
                "xbf": "application/octet-stream",
            }
            response = await send_file(
                store.project_dir(project_id) / relative,
                as_attachment=True,
                conditional=True,
                mimetype=mimetypes.get(kind),
            )
            if kind.lower() == "xbf":
                state = store.get_editor(project_id)
                if state.get("revision") != state.get("saved_revision"):
                    response.headers["X-CascadeCAD-Uncommitted-Edits"] = "true"
            return response
        except (ValueError, FileNotFoundError):
            abort(404)

    return app


app = create_app()


# --- Background Worker Lifespan Loop ---
import asyncio
from .config import Settings
from .store import Store
from .worker import run_job

async def _bg_worker_loop():
    settings = Settings.from_env()
    store = Store(settings.storage)
    poll_sec = getattr(settings, "worker_poll_seconds", 2) or 2
    app.logger.info("[+] Background worker loop initialized.")

    while True:
        try:
            jobs = await asyncio.to_thread(store.queued_jobs)
            for job in jobs:
                app.logger.info(f"[+] Processing job {job['id']}...")
                await asyncio.to_thread(run_job, store, settings, job)
        except asyncio.CancelledError:
            break
        except Exception as e:
            app.logger.error(f"[!] Worker task error: {e}")

        await asyncio.sleep(poll_sec)

@app.while_serving
async def lifespan():
    worker_task = asyncio.create_task(_bg_worker_loop())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
