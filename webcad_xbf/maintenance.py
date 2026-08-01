from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Iterable

from .config import Settings
from .store import Store, read_json


def tree_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TiB"


def age_seconds(path: Path, metadata: dict | None = None) -> float:
    stamp = 0.0
    if metadata:
        stamp = float(metadata.get("completed_at") or metadata.get("updated_at") or metadata.get("created_at") or 0)
    if not stamp:
        try:
            stamp = path.stat().st_mtime
        except OSError:
            stamp = time.time()
    return max(0.0, time.time() - stamp)


def remove(path: Path, execute: bool, actions: list[str], reason: str) -> None:
    actions.append(f"{'REMOVE' if execute else 'WOULD REMOVE'} {path} — {reason} ({human_size(tree_size(path))})")
    if not execute:
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def active_project_ids(store: Store) -> set[str]:
    active: set[str] = set()
    for job_path in store.jobs.glob("job_*.json"):
        try:
            job = read_json(job_path)
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") not in {"queued", "running"}:
            continue
        project_id = str(job.get("project_id") or "")
        if project_id:
            active.add(project_id)
        active.update(str(value) for value in (job.get("payload", {}).get("source_project_ids") or []))
    for project in store.list_projects():
        if project.get("status") in {"queued", "processing"}:
            active.add(str(project.get("id")))
    return active


def report_projects(store: Store) -> list[str]:
    rows = []
    total = 0
    for project in store.list_projects():
        size = tree_size(store.project_dir(project["id"]))
        total += size
        rows.append(
            f"{project['id']}  {human_size(size):>10}  {project.get('status', 'unknown'):<10}  "
            f"{project.get('name', '')}"
        )
    rows.append(f"TOTAL PROJECT DATA: {human_size(total)}")
    disk = shutil.disk_usage(store.root)
    rows.append(f"FILESYSTEM FREE: {human_size(disk.free)} of {human_size(disk.total)}")
    return rows


def cleanup(
    store: Store,
    *,
    execute: bool,
    upload_hours: float,
    job_days: float,
    temp_hours: float,
    keep_revisions: int,
    remove_sources: bool,
    delete_failed_days: float | None,
    delete_project_ids: Iterable[str],
) -> list[str]:
    actions: list[str] = []
    active = active_project_ids(store)
    upload_age = upload_hours * 3600
    job_age = job_days * 86400
    temp_age = temp_hours * 3600

    for project_id in delete_project_ids:
        if project_id in active:
            actions.append(f"SKIP {project_id} — active project")
            continue
        try:
            project_dir = store.project_dir(project_id)
            actions.append(
                f"{'DELETE' if execute else 'WOULD DELETE'} PROJECT {project_id} ({human_size(tree_size(project_dir))})"
            )
            if execute:
                store.delete_project(project_id)
        except (ValueError, FileNotFoundError) as exc:
            actions.append(f"SKIP {project_id} — {exc}")

    for upload_dir in store.uploads.glob("upl_*"):
        try:
            metadata = read_json(upload_dir / "upload.json")
        except (OSError, json.JSONDecodeError, FileNotFoundError):
            if age_seconds(upload_dir) >= upload_age:
                remove(upload_dir, execute, actions, "unreadable abandoned upload")
            continue
        project_id = str(metadata.get("project_id") or "")
        if project_id in active:
            continue
        if age_seconds(upload_dir, metadata) < upload_age:
            continue
        reason = "completed upload metadata" if metadata.get("complete") else "abandoned partial upload"
        remove(upload_dir, execute, actions, reason)
        if not metadata.get("complete"):
            try:
                manifest = store.get_project(project_id)
                project_dir = store.project_dir(project_id)
                if manifest.get("status") == "uploading" and not (project_dir / "master.xbf").exists():
                    remove(project_dir, execute, actions, "empty project belonging to abandoned upload")
            except (ValueError, FileNotFoundError, OSError):
                pass

    for job_path in store.jobs.glob("job_*.json"):
        try:
            job = read_json(job_path)
        except (OSError, json.JSONDecodeError):
            if age_seconds(job_path) >= job_age:
                remove(job_path, execute, actions, "unreadable old job record")
            continue
        if job.get("status") in {"complete", "failed"} and age_seconds(job_path, job) >= job_age:
            remove(job_path, execute, actions, f"old {job.get('status')} job record")

    for project in store.list_projects():
        project_id = project["id"]
        if project_id in active:
            continue
        project_dir = store.project_dir(project_id)

        revisions = sorted(
            (path for path in (project_dir / "revisions").glob("rev_*") if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old_revision in revisions[max(0, keep_revisions):]:
            remove(old_revision, execute, actions, f"revision beyond newest {keep_revisions}")

        if remove_sources and project.get("status") == "ready" and (project_dir / "master.xbf").exists():
            for source in (project_dir / "source").glob("*"):
                if source.is_file():
                    remove(source, execute, actions, "original import retained after valid XBF creation")

        if delete_failed_days is not None and project.get("status") == "failed":
            threshold = delete_failed_days * 86400
            if max(0.0, time.time() - float(project.get("updated_at", 0) or 0)) >= threshold:
                remove(project_dir, execute, actions, f"failed project older than {delete_failed_days:g} days")

    for temp in store.root.rglob(".*.tmp*"):
        if temp.is_file() and age_seconds(temp) >= temp_age:
            remove(temp, execute, actions, "stale temporary file")

    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report and safely clean CascadeCAD storage")
    parser.add_argument("--execute", action="store_true", help="Perform removals; default is dry-run")
    parser.add_argument("--uploads-older-hours", type=float, default=24.0)
    parser.add_argument("--jobs-older-days", type=float, default=7.0)
    parser.add_argument("--temp-older-hours", type=float, default=24.0)
    parser.add_argument("--keep-revisions", type=int, default=5)
    parser.add_argument("--remove-sources", action="store_true", help="Remove original uploads after master.xbf exists")
    parser.add_argument("--delete-failed-projects-days", type=float, default=None)
    parser.add_argument("--delete-project", action="append", default=[], metavar="PROJECT_ID")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    store = Store(settings.storage)
    print("CascadeCAD storage report")
    for row in report_projects(store):
        print(row)
    print("\nCleanup plan" + (" (EXECUTING)" if args.execute else " (DRY RUN)"))
    actions = cleanup(
        store,
        execute=args.execute,
        upload_hours=max(0.0, args.uploads_older_hours),
        job_days=max(0.0, args.jobs_older_days),
        temp_hours=max(0.0, args.temp_older_hours),
        keep_revisions=max(0, args.keep_revisions),
        remove_sources=args.remove_sources,
        delete_failed_days=args.delete_failed_projects_days,
        delete_project_ids=args.delete_project,
    )
    if actions:
        for action in actions:
            print(action)
    else:
        print("Nothing eligible for cleanup.")
    if not args.execute:
        print("\nNo files were changed. Add --execute after reviewing the plan.")


if __name__ == "__main__":
    main()
