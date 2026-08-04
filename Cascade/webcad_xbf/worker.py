from __future__ import annotations

import os
import signal
import sys
import time
import traceback
from pathlib import Path

from .config import Settings
from .editor import mark_saved
from .geometry import (
    GeometryJobCancelled,
    combine_projects,
    commit_editor,
    convert_to_faceted_solids,
    export_project_file,
    import_project,
    model_operation,
    split_component,
)
from .store import Store

_STOP = False


def _stop(_signum, _frame) -> None:
    global _STOP
    _STOP = True


def run_job(store: Store, settings: Settings, job: dict) -> None:
    job_id = job["id"]
    project_id = job["project_id"]
    project_dir = store.project_dir(project_id)

    def progress(value: int, message: str) -> None:
        store.update_job(job_id, progress=max(0, min(100, value)), message=message)
        store.update_project(project_id, status="processing", message=message)
        store.set_worker_status(state="working", job_id=job_id, project_id=project_id, message=message)

    store.update_job(job_id, status="running", progress=1, message="Starting")
    store.set_worker_status(state="working", job_id=job_id, project_id=project_id, message="Starting job")
    try:
        operation = job["operation"]
        if operation == "import":
            source = Path(job["payload"]["source"])
            result = import_project(
                source=source,
                project_dir=project_dir,
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
                cleanup_mesh=bool(job.get("payload", {}).get("mesh_cleanup", False)),
            )
            store.update_project(project_id, status="ready", **result)
            store.reset_editor(project_id, result["components"])

        elif operation == "commit_edits":
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            result = commit_editor(
                project_dir=project_dir,
                geometry_kind=manifest.get("geometry_kind") or "unknown",
                editor_state=state,
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
            )
            saved_state = mark_saved(state, result["components"])
            store.save_editor(project_id, saved_state)
            store.update_project(
                project_id,
                status="ready",
                components=result["components"],
                step_export=None,
                step_export_report=None,
                revision_id=result["revision_id"],
                message=result["message"],
            )

        elif operation == "combine_projects":
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            source_ids = list(job.get("payload", {}).get("source_project_ids") or [])
            sources = []
            for source_id in source_ids:
                source_manifest = store.get_project(str(source_id))
                sources.append(
                    {
                        "project_id": source_manifest["id"],
                        "name": source_manifest.get("name") or source_manifest["id"],
                        "geometry_kind": source_manifest.get("geometry_kind") or "unknown",
                        "master_path": str(store.project_dir(source_manifest["id"]) / "master.xbf"),
                        "editor_state": store.get_editor(source_manifest["id"]),
                    }
                )
            result = combine_projects(
                project_dir=project_dir,
                target_geometry_kind=manifest.get("geometry_kind") or "unknown",
                target_editor_state=state,
                sources=sources,
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
            )
            saved_state = mark_saved(state, result["components"])
            store.save_editor(project_id, saved_state)
            previous_combined = list(manifest.get("combined_projects") or [])
            store.update_project(
                project_id,
                status="ready",
                components=result["components"],
                geometry_kind=result["geometry_kind"],
                combined_projects=previous_combined + result["combined_projects"],
                step_export=None,
                step_export_report=None,
                revision_id=result["revision_id"],
                message=result["message"],
            )

        elif operation == "split_component":
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            result = split_component(
                project_dir=project_dir,
                geometry_kind=manifest.get("geometry_kind") or "unknown",
                editor_state=state,
                component_id=str(job["payload"]["component_id"]),
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
            )
            saved_state = mark_saved(state, result["components"])
            store.save_editor(project_id, saved_state)
            store.update_project(
                project_id,
                status="ready",
                components=result["components"],
                step_export=None,
                step_export_report=None,
                revision_id=result["revision_id"],
                message=result["message"],
            )

        elif operation == "model_operation":
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            payload = job.get("payload", {})
            result = model_operation(
                project_dir=project_dir,
                geometry_kind=manifest.get("geometry_kind") or "unknown",
                editor_state=state,
                operation=str(payload.get("operation", "")),
                component_ids=list(payload.get("component_ids") or []),
                parameters=dict(payload.get("parameters") or {}),
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
            )
            saved_state = mark_saved(state, result["components"])
            store.save_editor(project_id, saved_state)
            store.update_project(
                project_id,
                status="ready",
                components=result["components"],
                geometry_kind=result["geometry_kind"],
                step_export=None,
                step_export_report=None,
                revision_id=result["revision_id"],
                message=result["message"],
            )

        elif operation == "convert_faceted_solids":
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            payload = job.get("payload", {})
            result = convert_to_faceted_solids(
                project_dir=project_dir,
                geometry_kind=manifest.get("geometry_kind") or "unknown",
                editor_state=state,
                preview_tolerance=settings.preview_tolerance,
                preview_angular_tolerance=settings.preview_angular_tolerance,
                progress=progress,
                should_cancel=lambda: store.job_cancel_requested(job_id),
                max_triangles=settings.max_faceted_step_triangles,
                timeout_seconds=settings.step_export_timeout_seconds,
                fast_render=bool(payload.get("fast_render", False)),
                faceted_workers=settings.faceted_workers,
                faceted_queue_depth=settings.faceted_queue_depth,
                faceted_memory_budget_gb=settings.faceted_memory_budget_gb,
                faceted_cache_enabled=settings.faceted_cache_enabled,
                faceted_cache_max_bytes=settings.faceted_cache_max_bytes,
                faceted_direct_ocp=settings.faceted_direct_ocp,
                faceted_freecad_fallback=settings.faceted_freecad_fallback,
                faceted_unify_same_domain=settings.faceted_unify_same_domain,
            )
            saved_state = mark_saved(state, result["components"])
            store.save_editor(project_id, saved_state)
            conversion_report = {
                key: value for key, value in result.items()
                if key not in {"components", "message", "geometry_kind"}
            }
            store.update_project(
                project_id,
                status="ready",
                components=result["components"],
                geometry_kind=result["geometry_kind"],
                revision_id=result.get("revision_id"),
                faceted_conversion_report=conversion_report,
                exports={},
                last_export=None,
                last_export_format=None,
                last_export_report=None,
                xbf_export=None,
                xbf_export_report=None,
                step_export=None,
                step_export_report=None,
                csg_export=None,
                csg_export_report=None,
                brep_export=None,
                brep_export_report=None,
                fcstd_export=None,
                fcstd_export_report=None,
                message=result["message"],
            )
            store.update_job(job_id, result=conversion_report)

        elif operation in {"export_file", "export_step"}:
            manifest = store.get_project(project_id)
            state = store.get_editor(project_id)
            payload = job.get("payload", {})
            export_format = "step" if operation == "export_step" else str(payload.get("format", "")).lower()
            report = export_project_file(
                project_dir=project_dir,
                geometry_kind=manifest.get("geometry_kind") or "unknown",
                editor_state=state,
                progress=progress,
                export_format=export_format,
                component_ids=list(payload.get("component_ids") or []),
                unit_system=str(payload.get("unit_system", "imperial")),
                should_cancel=lambda: store.job_cancel_requested(job_id),
                max_faceted_triangles=settings.max_faceted_step_triangles,
                step_timeout_seconds=settings.step_export_timeout_seconds,
                faceted_chunk_triangles=settings.faceted_step_chunk_triangles,
                max_csg_triangles=settings.max_csg_triangles,
                fast_render=bool(payload.get("fast_render", False)),
                faceted_workers=settings.faceted_workers,
                faceted_queue_depth=settings.faceted_queue_depth,
                faceted_memory_budget_gb=settings.faceted_memory_budget_gb,
                faceted_cache_enabled=settings.faceted_cache_enabled,
                faceted_cache_max_bytes=settings.faceted_cache_max_bytes,
                faceted_direct_ocp=settings.faceted_direct_ocp,
                faceted_freecad_fallback=settings.faceted_freecad_fallback,
                faceted_unify_same_domain=settings.faceted_unify_same_domain,
            )
            exports = dict(manifest.get("exports") or {})
            exports[export_format] = report
            updates = {
                "status": "ready",
                "exports": exports,
                "last_export_format": export_format,
                "last_export": report["relative_path"],
                "last_export_report": report,
                "message": f"{export_format.upper()} export ready",
            }
            if export_format == "step":
                updates.update(step_export=report["relative_path"], step_export_report=report)
            elif export_format == "csg":
                updates.update(csg_export=report["relative_path"], csg_export_report=report)
            elif export_format == "brep":
                updates.update(brep_export=report["relative_path"], brep_export_report=report)
            elif export_format == "fcstd":
                updates.update(fcstd_export=report["relative_path"], fcstd_export_report=report)
            elif export_format == "xbf":
                updates.update(xbf_export=report["relative_path"], xbf_export_report=report)
            store.update_project(project_id, **updates)
            store.update_job(job_id, result=report)
        else:
            raise ValueError(f"Unknown operation: {operation}")
        if store.job_cancel_requested(job_id):
            raise GeometryJobCancelled("Export cancelled")
        store.update_job(job_id, status="complete", progress=100, message="Complete", finished_at=time.time())
        store.set_worker_status(state="idle", job_id=None, project_id=None, message="Job complete")
    except GeometryJobCancelled as exc:
        store.update_job(job_id, status="cancelled", message=str(exc), error=None, finished_at=time.time())
        store.update_project(project_id, status="ready", message=str(exc))
        store.set_worker_status(state="idle", job_id=None, project_id=None, message=str(exc))
    except Exception as exc:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:]
        store.update_job(job_id, status="failed", message=str(exc), error=detail)
        store.update_project(project_id, status="failed", message=str(exc))
        store.set_worker_status(state="idle", job_id=None, project_id=None, message=f"Job failed: {exc}")


def main() -> None:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    settings = Settings.from_env()
    store = Store(settings.storage)
    recovery = store.recover_interrupted_jobs(settings.job_recovery_limit)
    store.set_worker_status(
        state="idle",
        pid=os.getpid(),
        job_id=None,
        project_id=None,
        message=f"Worker started; recovered {recovery['recovered']} job(s), failed {recovery['failed']}",
    )
    last_idle_heartbeat = 0.0
    while not _STOP:
        jobs = store.queued_jobs()
        if not jobs:
            now = time.time()
            if now - last_idle_heartbeat >= 10.0:
                store.set_worker_status(state="idle", pid=os.getpid(), job_id=None, project_id=None, message="Waiting for jobs")
                last_idle_heartbeat = now
            time.sleep(settings.worker_poll_seconds)
            continue
        run_job(store, settings, jobs[0])
        if not _STOP:
            # CadQuery/OCCT and mesh libraries can retain large native arenas.
            # Re-exec after every geometry job to return all memory to Linux.
            store.set_worker_status(
                state="restarting",
                pid=os.getpid(),
                job_id=None,
                project_id=None,
                message="Recycling worker memory after job",
            )
            os.execv(sys.executable, [sys.executable, "-m", "webcad_xbf.worker"])
    store.set_worker_status(state="stopped", pid=os.getpid(), job_id=None, project_id=None, message="Worker stopped")


if __name__ == "__main__":
    main()
