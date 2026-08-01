import os
import time
from pathlib import Path

from webcad_xbf.maintenance import cleanup
from webcad_xbf.store import Store


def test_running_job_recovery_then_failure(tmp_path: Path):
    store = Store(tmp_path)
    project = store.create_project("Truck", "truck.step")
    store.update_project(project["id"], status="processing")
    job = store.create_job("import", project["id"], {"source": "truck.step"})
    store.update_job(job["id"], status="running")

    first = store.recover_interrupted_jobs(recovery_limit=1)
    recovered = store.get_job(job["id"])
    assert first == {"recovered": 1, "failed": 0}
    assert recovered["status"] == "queued"
    assert recovered["attempts"] == 1

    store.update_job(job["id"], status="running")
    second = store.recover_interrupted_jobs(recovery_limit=1)
    failed = store.get_job(job["id"])
    assert second == {"recovered": 0, "failed": 1}
    assert failed["status"] == "failed"
    assert "memory pressure" in failed["message"]


def test_cleanup_dry_run_and_execute(tmp_path: Path):
    store = Store(tmp_path)
    project = store.create_project("Abandoned", "abandoned.3mf")
    upload = store.create_upload(project["id"], "abandoned.3mf", 100)
    upload_dir = store.upload_dir(upload["id"])
    old = time.time() - 48 * 3600
    os.utime(upload_dir, (old, old))
    metadata_path = upload_dir / "upload.json"
    import json
    metadata = json.loads(metadata_path.read_text())
    metadata["created_at"] = old
    metadata_path.write_text(json.dumps(metadata))
    os.utime(metadata_path, (old, old))

    plan = cleanup(
        store,
        execute=False,
        upload_hours=24,
        job_days=7,
        temp_hours=24,
        keep_revisions=5,
        remove_sources=False,
        delete_failed_days=None,
        delete_project_ids=[],
    )
    assert any("abandoned partial upload" in row for row in plan)
    assert upload_dir.exists()

    cleanup(
        store,
        execute=True,
        upload_hours=24,
        job_days=7,
        temp_hours=24,
        keep_revisions=5,
        remove_sources=False,
        delete_failed_days=None,
        delete_project_ids=[],
    )
    assert not upload_dir.exists()
    assert not store.project_dir(project["id"]).exists()
